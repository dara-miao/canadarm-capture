"""What the controller is told about the grapple pin.

A real arm does not know where the pin is. It estimates the pin's pose from a
camera view of a target, and when the arm is flown from the ground the picture
arrives late. This module stands in for that chain with three effects: a fixed
delay, a limited update rate, and random error on each update.

Velocities are passed through with the same delay but no added error, as if
from a separate rate estimate. That is a simplification.
"""

from collections import deque
from dataclasses import dataclass

import mujoco
import numpy as np


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cross product of two 3-vectors. Several times faster than np.cross at this size."""
    return np.array([a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]])


@dataclass
class SensorConfig:
    delay: float = 0.0  # age of the newest measurement the controller sees [s]
    rate: float = 0.0  # measurements per second; 0 means one every simulation step
    pos_noise: float = 0.0  # standard deviation of pin-tip position error, per axis [m]
    angle_noise: float = 0.0  # standard deviation of pin-axis direction error [rad]


@dataclass
class PinObservation:
    tip: np.ndarray  # pin tip position, world frame [m]
    axis: np.ndarray  # unit vector along the pin, base to tip, world frame
    v_tip: np.ndarray  # pin tip velocity, world frame [m/s]
    w: np.ndarray  # vehicle angular velocity, world frame [rad/s]


class PinSensor:
    def __init__(self, model: mujoco.MjModel, config: SensorConfig | None = None, seed: int = 0):
        self.model = model
        self.cfg = config or SensorConfig()
        self.seed = seed
        self.tip_id = model.site("pin_tip").id

    def reset(self, data: mujoco.MjData) -> None:
        self.rng = np.random.default_rng(self.seed)
        self.history: deque[tuple[float, PinObservation]] = deque()
        self.latest: PinObservation | None = None
        self.next_update = data.time

    def _truth(self, data: mujoco.MjData) -> PinObservation:
        vel = np.empty(6)
        mujoco.mj_objectVelocity(self.model, data, mujoco.mjtObj.mjOBJ_SITE, self.tip_id, vel, 0)
        return PinObservation(
            tip=data.site("pin_tip").xpos.copy(),
            axis=data.body("fixture").xmat.reshape(3, 3)[:, 0].copy(),
            v_tip=vel[3:].copy(),
            w=vel[:3].copy(),
        )

    def observe(self, data: mujoco.MjData) -> PinObservation:
        """The controller's current view of the pin. Call once per simulation step.

        Returns a new object whenever there is a new pose reading, and the same object otherwise.
        """
        cfg = self.cfg
        self.history.append((data.time, self._truth(data)))
        # Keep only the newest entry that is at least `delay` old, plus everything after it.
        while len(self.history) > 1 and self.history[1][0] <= data.time - cfg.delay:
            self.history.popleft()

        obs = self.history[0][1]
        if self.latest is None or data.time >= self.next_update:
            tip, axis = obs.tip, obs.axis
            if cfg.pos_noise > 0:
                tip = tip + self.rng.normal(0.0, cfg.pos_noise, 3)
            if cfg.angle_noise > 0:
                tilt = self.rng.normal(0.0, cfg.angle_noise, 3)
                axis = axis + _cross(tilt, axis)
                axis = axis / np.linalg.norm(axis)
            self.latest = PinObservation(tip, axis, obs.v_tip, obs.w)
            if cfg.rate > 0:
                self.next_update += 1.0 / cfg.rate
        else:
            # Between pose readings only the velocities are refreshed.
            self.latest.v_tip, self.latest.w = obs.v_tip, obs.w
        return self.latest
