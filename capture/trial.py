"""Run one capture attempt and report how it ended."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

import mujoco
import numpy as np

from . import scene
from .controller import CaptureController, Phase

SEATED_DEPTH = 0.30  # pin length: the fixture plate rests on the rim [m]
SEATED_TOL = 0.01
LATERAL_TOL = 0.01
REL_SPEED_TOL = 0.002  # [m/s]
# The pin counts as still held if its tip is inside the cavity, behind the snare plane.
HELD_DEPTH = 0.15  # [m]
HELD_LATERAL = 0.10  # [m]

# Retention check, run after a capture that seated and latched. The Shuttle arm's end
# effector had to carry 1,627 N m of bending, the "arm joint locked motor" load case,
# with at most 3 degrees of separation at the interface (Daniell and Sachdev, 1982).
# No such figure was found for Canadarm2's, so this is a borrowed target.
RETENTION_MOMENT = 1627.0  # [N m]
RETENTION_ANGLE = np.radians(3.0)
RETENTION_TIME = 5.0  # [s]


class Outcome(Enum):
    CAPTURED = "captured"  # seated, latched, and held through the retention check
    CAUGHT_NOT_RIGID = "caught_not_rigid"  # snare holds the pin, but the capture did not seat, latch, or hold
    LOST = "lost"  # the snare closed on the pin, and the pin later escaped
    MISSED = "missed"  # the snare fired and closed on nothing
    OUT_OF_REACH = "out_of_reach"  # controller gave up before firing: arm at the edge of its workspace
    TIMED_OUT = "timed_out"  # snare never fired within the time allowed


@dataclass
class TrialResult:
    outcome: Outcome
    phase: Phase  # phase the controller was in when the trial ended
    duration: float  # simulated time [s]
    t_trigger: float | None  # when the snare fired [s]
    offset: np.ndarray  # final pin tip position in the mouth frame [m]
    axis_error: float  # final angle between the pin and the approach axis [rad]
    rel_speed: float  # final pin-tip speed relative to the end effector [m/s]
    conditioning: float  # smallest Jacobian singular value seen while tracking
    engaged: bool = False  # the pin was inside the snare when it finished closing
    seated: bool = False  # pull-in ended with the fixture on the rim, on axis, at rest
    latched: bool = False  # the latches engaged
    retained: bool = False  # the joint held through the retention check
    catchable_time: float = 0.0  # how long after firing the pin stayed catchable, up to the snare's closing time [s]
    retention_tilt: float = 0.0  # largest pin tilt during the retention check [rad]

    @property
    def success(self) -> bool:
        return self.outcome is Outcome.CAPTURED


def relative_speed(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    v_tip, v_mouth = np.empty(6), np.empty(6)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("pin_tip").id, v_tip, 0)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("lee_mouth").id, v_mouth, 0)
    return float(np.linalg.norm(v_tip[3:] - v_mouth[3:]))


def is_seated(phase: Phase, offset: np.ndarray, rel_speed: float) -> bool:
    lateral = float(np.linalg.norm(offset[:2]))
    return bool(
        phase is Phase.DONE
        and abs(offset[2] + SEATED_DEPTH) < SEATED_TOL
        and lateral < LATERAL_TOL
        and rel_speed < REL_SPEED_TOL
    )


def classify(
    phase: Phase, fired: bool, offset: np.ndarray, engaged: bool, seated: bool, latched: bool, retained: bool
) -> Outcome:
    """Label how an attempt ended, from the true final state.

    offset is the pin's position after the retention check, if one was run.
    """
    if phase is Phase.ABORTED:
        return Outcome.OUT_OF_REACH
    if not fired:
        return Outcome.TIMED_OUT
    lateral = float(np.linalg.norm(offset[:2]))
    if offset[2] > -HELD_DEPTH or lateral > HELD_LATERAL:
        return Outcome.LOST if engaged else Outcome.MISSED
    if seated and latched and retained:
        return Outcome.CAPTURED
    return Outcome.CAUGHT_NOT_RIGID


def _step(model: mujoco.MjModel, data: mujoco.MjData, controller: CaptureController, on_step) -> None:
    mujoco.mj_step1(model, data)
    data.qfrc_applied[:] = 0  # the controller's latch force and any test load are re-added each step
    controller.step(data)
    if on_step is not None:
        on_step(data)


def _retention_check(model, data, controller, on_step) -> tuple[bool, float]:
    """Lever the vehicle sideways with RETENTION_MOMENT and see whether the joint holds."""
    vehicle = model.body("vehicle").id
    worst = 0.0
    t_end = data.time + RETENTION_TIME
    while data.time < t_end:
        _step(model, data, controller, on_step)
        across = data.site("lee_mouth").xmat.reshape(3, 3)[:, 0]
        mujoco.mj_applyFT(
            model, data, np.zeros(3), RETENTION_MOMENT * across, data.site("pin_tip").xpos, vehicle, data.qfrc_applied
        )
        mujoco.mj_step2(model, data)
        worst = max(worst, scene.pin_axis_error(model, data))
    # let it come to rest again with the load removed
    t_end = data.time + 2.0
    while data.time < t_end:
        _step(model, data, controller, on_step)
        mujoco.mj_step2(model, data)
    mujoco.mj_forward(model, data)
    offset = scene.pin_offset(model, data)
    held = offset[2] < -HELD_DEPTH and np.linalg.norm(offset[:2]) < HELD_LATERAL
    return bool(held and worst < RETENTION_ANGLE), worst


def run_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    controller: CaptureController,
    max_time: float = 180.0,
    on_step: Callable[[mujoco.MjData], None] | None = None,
) -> TrialResult:
    """Step the simulation from its current state until the controller finishes or time runs out."""
    controller.reset(data)
    t0 = data.time
    while controller.phase not in (Phase.DONE, Phase.ABORTED) and data.time - t0 < max_time:
        _step(model, data, controller, on_step)
        mujoco.mj_step2(model, data)

    mujoco.mj_forward(model, data)
    duration = data.time - t0
    offset = scene.pin_offset(model, data)
    rel = relative_speed(model, data)
    axis_error = scene.pin_axis_error(model, data)
    seated = is_seated(controller.phase, offset, rel)
    latched = bool(controller.latched)
    retained, tilt = False, 0.0
    if seated and latched:
        retained, tilt = _retention_check(model, data, controller, on_step)
    return TrialResult(
        outcome=classify(
            controller.phase,
            controller.t_trigger is not None,
            scene.pin_offset(model, data),
            bool(controller.engaged),
            seated,
            latched,
            retained,
        ),
        phase=controller.phase,
        duration=duration,
        t_trigger=controller.t_trigger,
        offset=offset,
        axis_error=axis_error,
        rel_speed=rel,
        conditioning=controller.conditioning,
        engaged=bool(controller.engaged),
        seated=seated,
        latched=latched,
        retained=retained,
        catchable_time=controller.catchable_time,
        retention_tilt=tilt,
    )
