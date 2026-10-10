"""Approach and capture controller.

The arm tracks the grapple pin in three phases:

  ALIGN    hold a standoff in front of the pin until the end effector is lined up
  INSERT   advance along the pin axis until the pin tip is past the snare
  GRAPPLE  freeze the arm and run the snare sequence

Tracking is resolved-rate control: a desired end-effector velocity is mapped to
joint velocities through the damped pseudo-inverse of the Jacobian, then
integrated into joint position commands.

The controller reads the true pin pose and velocity from the simulator. A real
system would estimate these from a camera target; sensing error is a parameter
for later experiments, not part of this controller.
"""

from dataclasses import dataclass
from enum import Enum

import mujoco
import numpy as np

from . import scene, snare


class Phase(Enum):
    ALIGN = "align"
    INSERT = "insert"
    GRAPPLE = "grapple"
    DONE = "done"


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
    max_ang: float = 0.03  # cap on the corrective tip rotation rate [rad/s]
    max_joint_rate: float = 0.03  # [rad/s]
    dls_damping: float = 0.05
    settle_time: float = 5.0  # wait after the snare sequence before finishing [s]


def _clamp_norm(v: np.ndarray, limit: float) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n <= limit else v * (limit / n)


class CaptureController:
    def __init__(self, model: mujoco.MjModel, config: ControllerConfig | None = None):
        self.model = model
        self.cfg = config or ControllerConfig()
        self.n = len(scene.ARM_JOINTS)
        self.qadr = scene.arm_qpos_adr(model)
        self.dof = np.array([model.joint(j).dofadr[0] for j in scene.ARM_JOINTS])
        self.mouth_id = model.site("lee_mouth").id
        self.tip_id = model.site("pin_tip").id
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

    def step(self, data: mujoco.MjData) -> None:
        """Set data.ctrl. Call between mj_step1 and mj_step2."""
        cfg, model = self.cfg, self.model
        dt = model.opt.timestep
        offset = scene.pin_offset(model, data)
        lateral = np.linalg.norm(offset[:2])

        if self.phase is Phase.ALIGN:
            ok = (
                lateral < cfg.align_lateral
                and scene.pin_axis_error(model, data) < cfg.align_angle
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

        if self.phase in (Phase.ALIGN, Phase.INSERT):
            dq = self._tracking_rates(data)
            self.q_cmd += dq * dt
            data.ctrl[: self.n] = self.q_cmd + self.lead * dq
            scene.set_snare(model, data, 0.0, 0.0)
        else:
            data.ctrl[: self.n] = self.q_cmd  # arm holds still
            scene.set_snare(model, data, *snare.grapple_command(data.time - self.t_trigger))

    def _tracking_rates(self, data: mujoco.MjData) -> np.ndarray:
        cfg, model = self.cfg, self.model
        mouth = data.site("lee_mouth")
        z_l = mouth.xmat.reshape(3, 3)[:, 2]
        tip = data.site("pin_tip").xpos
        pin = data.body("vehicle").xmat.reshape(3, 3)[:, 0]

        # Pin tip velocity and vehicle angular velocity, world frame.
        vel = np.empty(6)
        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, self.tip_id, vel, 0)
        w_veh, v_tip = vel[:3], vel[3:]

        # Target: mouth on the pin axis at the commanded standoff, facing the pin.
        target = tip + self.standoff_cmd * pin
        v_target = v_tip + self.standoff_cmd * np.cross(w_veh, pin)
        v = _clamp_norm(cfg.kp_lin * (target - mouth.xpos), cfg.max_lin) + v_target
        # Roll about the pin axis is left free: the pin is symmetric.
        w = _clamp_norm(cfg.kp_ang * np.cross(z_l, -pin), cfg.max_ang) + w_veh - (w_veh @ pin) * pin

        jacp = np.empty((3, model.nv))
        jacr = np.empty((3, model.nv))
        mujoco.mj_jacSite(model, data, jacp, jacr, self.mouth_id)
        J = np.vstack([jacp[:, self.dof], jacr[:, self.dof]])
        twist = np.concatenate([v, w])
        dq = J.T @ np.linalg.solve(J @ J.T + cfg.dls_damping**2 * np.eye(6), twist)

        peak = np.abs(dq).max()
        if peak > cfg.max_joint_rate:
            dq *= cfg.max_joint_rate / peak
        return dq
