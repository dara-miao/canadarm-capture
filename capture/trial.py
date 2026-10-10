"""Run one capture attempt and report how it ended."""

from dataclasses import dataclass
from typing import Callable

import mujoco
import numpy as np

from . import scene
from .controller import CaptureController, Phase

SEATED_DEPTH = 0.30  # pin length: the fixture plate rests on the rim [m]
SEATED_TOL = 0.01
LATERAL_TOL = 0.01
REL_SPEED_TOL = 0.002  # [m/s]


@dataclass
class TrialResult:
    success: bool
    phase: Phase  # phase the controller was in when the trial ended
    duration: float  # simulated time [s]
    t_trigger: float | None  # when the snare fired [s]
    offset: np.ndarray  # final pin tip position in the mouth frame [m]
    rel_speed: float  # final pin-tip speed relative to the end effector [m/s]


def relative_speed(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    v_tip, v_mouth = np.empty(6), np.empty(6)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("pin_tip").id, v_tip, 0)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("lee_mouth").id, v_mouth, 0)
    return float(np.linalg.norm(v_tip[3:] - v_mouth[3:]))


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
    while controller.phase is not Phase.DONE and data.time - t0 < max_time:
        mujoco.mj_step1(model, data)
        controller.step(data)
        if on_step is not None:
            on_step(data)
        mujoco.mj_step2(model, data)

    mujoco.mj_forward(model, data)
    offset = scene.pin_offset(model, data)
    rel = relative_speed(model, data)
    success = (
        controller.phase is Phase.DONE
        and abs(offset[2] + SEATED_DEPTH) < SEATED_TOL
        and np.linalg.norm(offset[:2]) < LATERAL_TOL
        and rel < REL_SPEED_TOL
    )
    return TrialResult(success, controller.phase, data.time - t0, controller.t_trigger, offset, rel)
