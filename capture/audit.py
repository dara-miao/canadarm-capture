"""Checks that an attempt behaved like physics.

A contact simulation can give a confident, wrong result: forces no machine could make,
or motion that needs energy from nowhere. These checks watch every step of an attempt
and flag it when something like that happens. They do not say what went wrong, only
that the outcome should not be trusted.

The thresholds are first guesses. See the plan, experiment A.
"""

import mujoco
import numpy as np

# Everything the machine can apply to the vehicle is about 69 kN: the latches' 64 kN
# and the pull-in drive's 4.9 kN. Contact force beyond about twice that is not credible.
MAX_FORCE = 150e3  # [N]
# The vehicle should not leave a contact much faster than it has ever moved before one.
SPEED_RATIO, SPEED_MARGIN = 1.5, 0.02  # [-], [m/s]
MAX_OVERLAP = 0.01  # [m]
MAX_PAST_STOP = 0.005  # [m], for the sliding joints of the snare and carriage

FLAGS = ("unstable", "force", "energy", "overlap", "stop")


class Audit:
    """Call once per completed step; read `result()` at the end."""

    def __init__(self, model: mujoco.MjModel):
        self.model = model
        self.vehicle = model.body("vehicle").id
        self.vehicle_bodies = {self.vehicle, model.body("fixture").id}
        slides = [model.joint(n) for n in ("snare_0", "snare_1", "snare_2", "carriage_slide")]
        self.slide_q = np.array([j.qposadr[0] for j in slides])
        self.slide_lo = np.array([j.range[0] for j in slides])
        self.slide_hi = np.array([j.range[1] for j in slides])
        self.last_time = -np.inf
        self.unstable = False
        self.touched = False  # has the vehicle been in contact with anything yet
        self.speed_free = 0.0  # fastest the vehicle moved before its first contact [m/s]
        self.speed_after = 0.0  # fastest it moved from then on [m/s]
        self.peak_force = 0.0  # largest total contact force on the vehicle in one step [N]
        self.peak_overlap = 0.0  # deepest overlap between any two shapes [m]
        self.peak_past_stop = 0.0  # furthest a sliding joint went beyond its range [m]
        self._f = np.empty(6)
        self._v = np.empty(6)

    def __call__(self, data: mujoco.MjData) -> None:
        model = self.model
        if data.time < self.last_time:  # MuJoCo resets the state when a step goes unstable
            self.unstable = True
        self.last_time = data.time

        if data.ncon:
            self.peak_overlap = max(self.peak_overlap, float(-data.contact.dist[: data.ncon].min()))
            total = 0.0
            for i in range(data.ncon):
                c = data.contact[i]
                on_vehicle = (model.geom_bodyid[c.geom1] in self.vehicle_bodies) != (
                    model.geom_bodyid[c.geom2] in self.vehicle_bodies
                )
                if on_vehicle:
                    mujoco.mj_contactForce(model, data, i, self._f)
                    total += abs(self._f[0])
                    self.touched = True
            self.peak_force = max(self.peak_force, total)

        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, self.vehicle, self._v, 0)
        speed = float(np.linalg.norm(self._v[3:]))
        if self.touched:
            self.speed_after = max(self.speed_after, speed)
        else:
            self.speed_free = max(self.speed_free, speed)

        q = data.qpos[self.slide_q]
        past = max(float((self.slide_lo - q).max()), float((q - self.slide_hi).max()))
        self.peak_past_stop = max(self.peak_past_stop, past)

    def result(self, data: mujoco.MjData) -> dict:
        """The measurements, and which checks they fail, as columns for a results table."""
        unstable = self.unstable or any(int(w.number) for w in data.warning)
        failed = {
            "unstable": unstable,
            "force": self.peak_force > MAX_FORCE,
            "energy": self.touched and self.speed_after > SPEED_RATIO * self.speed_free + SPEED_MARGIN,
            "overlap": self.peak_overlap > MAX_OVERLAP,
            "stop": self.peak_past_stop > MAX_PAST_STOP,
        }
        return {
            "audit_peak_force": float(self.peak_force),
            "audit_speed_free": self.speed_free,
            "audit_speed_after": self.speed_after,
            "audit_peak_overlap": self.peak_overlap,
            "audit_peak_past_stop": self.peak_past_stop,
            "audit_flags": " ".join(name for name in FLAGS if failed[name]),
        }
