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


class Outcome(Enum):
    CAPTURED = "captured"  # pin seated, on axis, and at rest in the end effector
    CAUGHT_NOT_RIGID = "caught_not_rigid"  # snare holds the pin, but it is not seated or still moving
    MISSED = "missed"  # snare fired and the pin is not held
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

    @property
    def success(self) -> bool:
        return self.outcome is Outcome.CAPTURED


def relative_speed(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    v_tip, v_mouth = np.empty(6), np.empty(6)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("pin_tip").id, v_tip, 0)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("lee_mouth").id, v_mouth, 0)
    return float(np.linalg.norm(v_tip[3:] - v_mouth[3:]))


def classify(phase: Phase, fired: bool, offset: np.ndarray, rel_speed: float) -> Outcome:
    """Label how an attempt ended, from the true final state."""
    if phase is Phase.ABORTED:
        return Outcome.OUT_OF_REACH
    if not fired:
        return Outcome.TIMED_OUT
    lateral = float(np.linalg.norm(offset[:2]))
    if offset[2] > -HELD_DEPTH or lateral > HELD_LATERAL:
        return Outcome.MISSED
    seated = abs(offset[2] + SEATED_DEPTH) < SEATED_TOL and lateral < LATERAL_TOL
    if phase is Phase.DONE and seated and rel_speed < REL_SPEED_TOL:
        return Outcome.CAPTURED
    return Outcome.CAUGHT_NOT_RIGID


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
        mujoco.mj_step1(model, data)
        controller.step(data)
        if on_step is not None:
            on_step(data)
        mujoco.mj_step2(model, data)

    mujoco.mj_forward(model, data)
    offset = scene.pin_offset(model, data)
    rel = relative_speed(model, data)
    return TrialResult(
        outcome=classify(controller.phase, controller.t_trigger is not None, offset, rel),
        phase=controller.phase,
        duration=data.time - t0,
        t_trigger=controller.t_trigger,
        offset=offset,
        axis_error=scene.pin_axis_error(model, data),
        rel_speed=rel,
        conditioning=controller.conditioning,
    )
