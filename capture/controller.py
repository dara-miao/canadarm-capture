"""Approach and capture controller.

The arm tracks the grapple pin in three phases:

  ALIGN    hold a standoff in front of the pin until the end effector is lined up
  INSERT   advance along the pin axis until the pin tip is past the snare
  GRAPPLE  run the end effector's sequence: keep tracking while the snare closes,
           stop, go limp while the pin is pulled in and the latches engage, then
           hold position again. The latches engage only if pull-in seated the fixture.

Tracking is resolved-rate control: a desired end-effector velocity is mapped to
joint velocities through the damped pseudo-inverse of the Jacobian, then
integrated into joint position commands.

The controller sees the pin only through a PinSensor (capture/sensing.py), which
can delay and corrupt the measurements. It smooths them with a simple estimator:
between measurements the estimate moves with the reported velocity, and each new
measurement pulls it part of the way over. It makes no attempt to predict ahead
to cancel a delay. With the default sensor it sees the truth.
"""

from dataclasses import dataclass
from enum import Enum

import mujoco
import numpy as np

from . import scene, snare
from .sensing import PinObservation, PinSensor


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cross product of two 3-vectors. Several times faster than np.cross at this size."""
    return np.array([a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]])


class Phase(Enum):
    ALIGN = "align"
    INSERT = "insert"
    GRAPPLE = "grapple"
    DONE = "done"
    ABORTED = "aborted"  # the pin went out of reach before the snare fired


@dataclass
class ControllerConfig:
    hold_standoff: float = 0.4  # mouth-to-tip distance while aligning [m]
    insert_depth: float = 0.28  # commanded tip depth inside the cavity [m]
    trigger_depth: float = 0.25  # tip depth at which the snare fires [m]
    trigger_lateral: float = 0.05  # tip must be this close to the axis to fire [m]
    approach_speed: float = 0.03  # insertion speed along the pin axis [m/s]
    align_lateral: float = 0.01  # alignment tolerances before inserting
    align_angle: float = np.radians(1.0)
    align_standoff: float = 0.02
    align_dwell: float = 1.0  # tolerances must hold this long [s]
    kp_lin: float = 0.8  # position error gain [1/s]
    kp_ang: float = 0.8  # orientation error gain [1/s]
    max_lin: float = 0.10  # cap on the corrective tip speed [m/s]
    max_tip_speed: float = 0.37  # Canadarm2's published unloaded speed [m/s]
    max_ang: float = 0.03  # cap on the corrective tip rotation rate [rad/s]
    max_joint_rate: float = 0.03  # [rad/s]
    dls_damping: float = 0.05
    # Abort when the arm is nearly straight or folded and can no longer move its tip
    # freely: the smallest singular value of the Jacobian falls below this. It is
    # about 0.77 at the ready pose.
    min_conditioning: float = 0.15
    # Fraction of the way the pin estimate moves toward each new measurement.
    # 1 trusts every measurement fully; smaller values average out noise.
    measurement_gain: float = 0.2
    settle_time: float = 5.0  # wait after the snare sequence before finishing [s]
    # The Shuttle arm's end effector removes angular misalignment "against a limped arm":
    # joints with low resistance to being back-driven, except wrist roll.
    limp_during_pull_in: bool = True
    # Go limp as soon as the snare has closed, instead of holding position through the
    # pause before pull-in. Off by default; an option for studying lost captures.
    limp_from_snare_close: bool = False
    # Honda et al. (2014) hold the base-side shoulder roll joint fixed when solving the
    # arm's pose for a capture. Off by default; on makes poses comparable to theirs.
    lock_shoulder_roll: bool = False


# The pin can be snared while its tip is past the snare plane and short of the cavity floor.
CATCH_DEPTH = (0.221, 0.31)  # [m] inside the mouth
CATCH_LATERAL = 0.09  # [m]
# The latches engage only on a fixture that pull-in has seated.
SEATED_DEPTH, SEATED_TOL, SEATED_ANGLE = 0.30, 0.01, np.radians(1.0)


def _clamp_norm(v: np.ndarray, limit: float) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n <= limit else v * (limit / n)


class CaptureController:
    def __init__(
        self,
        model: mujoco.MjModel,
        config: ControllerConfig | None = None,
        sensor: PinSensor | None = None,
    ):
        self.model = model
        self.cfg = config or ControllerConfig()
        self.sensor = sensor or PinSensor(model)
        self.n = len(scene.ARM_JOINTS)
        self.qadr = scene.arm_qpos_adr(model)
        self.dof = np.array([model.joint(j).dofadr[0] for j in scene.ARM_JOINTS])
        self.mouth_id = model.site("lee_mouth").id
        # The joint servos damp joint velocity, so a moving command lags by kv/kp
        # seconds. Leading the command by that much cancels the lag.
        act = [model.actuator("a_" + j).id for j in scene.ARM_JOINTS]
        self.lead = -model.actuator_biasprm[act, 2] / model.actuator_gainprm[act, 0]

    def reset(self, data: mujoco.MjData) -> None:
        self.phase = Phase.ALIGN
        self.q_cmd = data.qpos[self.qadr].copy()
        self.standoff_cmd = self.cfg.hold_standoff
        self.aligned_since = None
        self.t_trigger = None
        self.holding_after_pull_in = False
        self.conditioning = np.inf  # smallest Jacobian singular value seen while tracking
        # Records for analysis, read from the true state. Only `latched` affects control,
        # standing in for the end effector's own position switches.
        self.engaged: bool | None = None  # was the pin inside the snare when it finished closing
        self.latched: bool | None = None  # did the latches engage
        self.catchable_time = 0.0  # how long after firing the pin stayed catchable, up to CLOSE_TIME [s]
        self._left_catch_zone = False
        self.close_speed = 0.0  # pin speed relative to the end effector when the snare finished closing [m/s]
        self.sensor.reset(data)
        self.estimate: PinObservation | None = None
        self.last_measurement: PinObservation | None = None

    def step(self, data: mujoco.MjData) -> None:
        """Set data.ctrl. Call between mj_step1 and mj_step2."""
        cfg, model = self.cfg, self.model
        dt = model.opt.timestep
        obs = self._update_estimate(self.sensor.observe(data), dt)
        # Where the controller believes the pin is, in the end-effector mouth frame.
        mouth = data.site("lee_mouth")
        R_l = mouth.xmat.reshape(3, 3)
        offset = R_l.T @ (obs.tip - mouth.xpos)
        lateral = np.linalg.norm(offset[:2])
        axis_error = np.arccos(np.clip(-obs.axis @ R_l[:, 2], -1.0, 1.0))

        if self.phase is Phase.ABORTED:
            data.ctrl[: self.n] = self.q_cmd
            scene.set_snare(model, data, 0.0, 0.0)
            return

        if self.phase is Phase.ALIGN:
            ok = (
                lateral < cfg.align_lateral
                and axis_error < cfg.align_angle
                and abs(offset[2] - cfg.hold_standoff) < cfg.align_standoff
            )
            if not ok:
                self.aligned_since = None
            elif self.aligned_since is None:
                self.aligned_since = data.time
            elif data.time - self.aligned_since >= cfg.align_dwell:
                self.phase = Phase.INSERT
        elif self.phase is Phase.INSERT:
            self.standoff_cmd = max(self.standoff_cmd - cfg.approach_speed * dt, -cfg.insert_depth)
            if offset[2] <= -cfg.trigger_depth and lateral < cfg.trigger_lateral:
                self.phase = Phase.GRAPPLE
                self.t_trigger = data.time
        elif self.phase is Phase.GRAPPLE:
            if data.time - self.t_trigger >= snare.SEQUENCE_TIME + cfg.settle_time:
                self.phase = Phase.DONE

        since = None if self.t_trigger is None else data.time - self.t_trigger
        if since is not None:
            self._record(data, since)
        # Keep following the pin until the snare has closed on it; stopping at the trigger
        # lets a receding pin back out of the snare before it shuts.
        closing = self.phase is Phase.GRAPPLE and since < snare.CLOSE_TIME
        if self.phase in (Phase.ALIGN, Phase.INSERT) or closing:
            dq, conditioning = self._tracking_rates(data, obs)
            self.conditioning = min(self.conditioning, conditioning)
            if conditioning < cfg.min_conditioning and not closing:
                self.phase = Phase.ABORTED
                data.ctrl[: self.n] = self.q_cmd
                scene.set_snare(model, data, 0.0, 0.0)
                return
            self.q_cmd += dq * dt
            data.ctrl[: self.n] = self.q_cmd + self.lead * dq
            scene.set_snare(model, data, *(snare.grapple_command(since) if closing else (0.0, 0.0)))
        else:
            limp_start = snare.CLOSE_TIME if cfg.limp_from_snare_close else snare.CLOSE_TIME + snare.SETTLE_TIME
            pulling_in = limp_start <= since < snare.SEQUENCE_TIME
            if since >= snare.SEQUENCE_TIME and not self.holding_after_pull_in:
                self.q_cmd = data.qpos[self.qadr].copy()  # hold wherever the pull-in left the arm
                self.holding_after_pull_in = True
            data.ctrl[: self.n] = self.q_cmd
            if pulling_in and cfg.limp_during_pull_in:
                # Commanding each joint to where it is, led by its own velocity, makes the
                # servo torque exactly zero. Wrist roll (the last joint) stays held.
                limp = data.qpos[self.qadr] + self.lead * data.qvel[self.dof]
                data.ctrl[: self.n - 1] = limp[:-1]
            scene.set_snare(model, data, *snare.grapple_command(since))
            if self.latched:
                scene.apply_latch(model, data, snare.latch_command(since))

    def _record(self, data: mujoco.MjData, since: float) -> None:
        """Note, from the true state, how the grapple is going."""
        true = scene.pin_offset(self.model, data)
        depth, lateral = -true[2], float(np.linalg.norm(true[:2]))
        if since < snare.CLOSE_TIME:
            catchable = CATCH_DEPTH[0] <= depth <= CATCH_DEPTH[1] and lateral < CATCH_LATERAL
            if catchable and not self._left_catch_zone:
                self.catchable_time = since
            else:
                self._left_catch_zone = True
        elif self.engaged is None:
            self.engaged = bool(depth >= CATCH_DEPTH[0] - 0.006 and lateral < 0.03)
            self.close_speed = scene.relative_speed(self.model, data)
        if since >= snare.PULL_IN_END and self.latched is None:
            self.latched = bool(
                abs(depth - SEATED_DEPTH) < SEATED_TOL
                and lateral < SEATED_TOL
                and scene.pin_axis_error(self.model, data) < SEATED_ANGLE
            )

    def _update_estimate(self, measurement: PinObservation, dt: float) -> PinObservation:
        """Smooth the sensor's measurements into a running estimate of the pin."""
        if self.estimate is None:
            self.estimate = PinObservation(measurement.tip.copy(), measurement.axis.copy(), measurement.v_tip, measurement.w)
            self.last_measurement = measurement
            return self.estimate
        est = self.estimate
        est.v_tip, est.w = measurement.v_tip, measurement.w
        est.tip = est.tip + est.v_tip * dt
        est.axis = est.axis + _cross(est.w, est.axis) * dt
        if measurement is not self.last_measurement:  # the sensor produced a new reading
            k = self.cfg.measurement_gain
            est.tip = est.tip + k * (measurement.tip - est.tip)
            est.axis = est.axis + k * (measurement.axis - est.axis)
            self.last_measurement = measurement
        est.axis = est.axis / np.linalg.norm(est.axis)
        return est

    def _tracking_rates(self, data: mujoco.MjData, obs: PinObservation) -> tuple[np.ndarray, float]:
        """Joint rates that follow the observed pin, and the Jacobian's smallest singular value."""
        cfg, model = self.cfg, self.model
        mouth = data.site("lee_mouth")
        z_l = mouth.xmat.reshape(3, 3)[:, 2]
        tip, pin, v_tip, w_veh = obs.tip, obs.axis, obs.v_tip, obs.w

        # Target: mouth on the pin axis at the commanded standoff, facing the pin.
        target = tip + self.standoff_cmd * pin
        v_target = v_tip + self.standoff_cmd * _cross(w_veh, pin)
        v = _clamp_norm(cfg.kp_lin * (target - mouth.xpos), cfg.max_lin) + v_target
        v = _clamp_norm(v, cfg.max_tip_speed)
        # Roll about the pin axis is left free: the pin is symmetric.
        w = _clamp_norm(cfg.kp_ang * _cross(z_l, -pin), cfg.max_ang) + w_veh - (w_veh @ pin) * pin

        jacp = np.empty((3, model.nv))
        jacr = np.empty((3, model.nv))
        mujoco.mj_jacSite(model, data, jacp, jacr, self.mouth_id)
        J = np.vstack([jacp[:, self.dof], jacr[:, self.dof]])
        if cfg.lock_shoulder_roll:
            J[:, 0] = 0.0  # no motion is assigned to a joint the task cannot see
        twist = np.concatenate([v, w])
        dq = J.T @ np.linalg.solve(J @ J.T + cfg.dls_damping**2 * np.eye(6), twist)

        peak = np.abs(dq).max()
        if peak > cfg.max_joint_rate:
            dq *= cfg.max_joint_rate / peak
        return dq, float(np.linalg.svd(J, compute_uv=False)[-1])
