"""Diagnostic: what is touching what when the checks flag an attempt?

Replays attempts from experiment B's and C's scenario set and prints, for the first
moment a check's threshold is crossed and for the worst moment, which pairs of shapes
are in contact, how deeply, and with what force.

    python experiments/replay_flagged.py 9,10,107                # baseline model
    python experiments/replay_flagged.py 0,1 friction_pin=0.1    # with a build option

Prints only. Single process, a few seconds per attempt.
"""

import sys
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from capture import audit, batch, scene  # noqa: E402
from capture.controller import CaptureController  # noqa: E402
from capture.sensing import PinSensor, SensorConfig  # noqa: E402
from capture.trial import run_trial  # noqa: E402
from run_experiments import scenarios  # noqa: E402


def name_of(model: mujoco.MjModel, geom: int) -> str:
    return model.geom(geom).name or f"({model.body(model.geom_bodyid[geom]).name})"


def snapshot(model: mujoco.MjModel, data: mujoco.MjData, controller: CaptureController) -> dict:
    f = np.empty(6)
    pairs = []
    for i in range(data.ncon):
        c = data.contact[i]
        mujoco.mj_contactForce(model, data, i, f)
        pairs.append((abs(f[0]), -c.dist, f"{name_of(model, c.geom1)} ~ {name_of(model, c.geom2)}"))
    pairs.sort(reverse=True)
    since = None if controller.t_trigger is None else data.time - controller.t_trigger
    offset = scene.pin_offset(model, data)
    return {
        "time": data.time, "phase": controller.phase.name, "since_firing": since,
        "pin_depth": -offset[2], "pin_lateral": float(np.linalg.norm(offset[:2])),
        "tilt_deg": float(np.degrees(scene.pin_axis_error(model, data))),
        "arm_torque": float(np.abs(data.qfrc_actuator[:7]).max()),
        "pairs": pairs[:6], "total": sum(p[0] for p in pairs), "deepest": max((p[1] for p in pairs), default=0.0),
    }  # fmt: skip


def show(label: str, s: dict | None) -> None:
    if s is None:
        print(f"    {label}: never")
        return
    since = "before firing" if s["since_firing"] is None else f"{s['since_firing']:.2f} s after firing"
    print(f"    {label}: t={s['time']:.2f} s, {s['phase']}, {since}; pin depth {s['pin_depth']:.3f} m, "
          f"off axis {s['pin_lateral']:.3f} m, tilt {s['tilt_deg']:.1f} deg; largest arm torque {s['arm_torque']:.0f} N m")  # fmt: skip
    for force, depth, pair in s["pairs"]:
        print(f"        {pair:34s} force {force / 1e3:10.1f} kN   overlap {1000 * depth:7.2f} mm")


def main() -> None:
    chosen = [int(i) for i in sys.argv[1].split(",")]
    build = {}
    for arg in sys.argv[2:]:
        key, value = arg.split("=")
        build[key] = value if key == "rim" else float(value)
    model = scene.build_model(meshes=False, **build)
    base = scenarios("B", {})
    for index in chosen:
        s = base[index]
        data = mujoco.MjData(model)
        scene.reset(model, data, lateral=(s.lateral_x, s.lateral_y), tilt=(s.tilt_x, s.tilt_y), roll=s.roll)
        scene.set_vehicle_velocity(
            model, data, drift=(s.drift_x, s.drift_y, s.drift_z), tumble=(s.tumble_x, s.tumble_y, s.tumble_z)
        )
        sensor = PinSensor(
            model, SensorConfig(s.sensor_delay, s.sensor_rate, s.sensor_pos_noise, s.sensor_angle_noise), seed=s.seed
        )
        controller = CaptureController(model, sensor=sensor)
        seen = {"first_contact": None, "first_force": None, "first_overlap": None, "worst_force": None, "worst_overlap": None}

        def after_step(d: mujoco.MjData) -> None:
            if not d.ncon:
                return
            snap = snapshot(model, d, controller)
            if seen["first_contact"] is None:
                seen["first_contact"] = snap
            if seen["first_force"] is None and snap["total"] > audit.MAX_FORCE:
                seen["first_force"] = snap
            if seen["first_overlap"] is None and snap["deepest"] > audit.MAX_OVERLAP:
                seen["first_overlap"] = snap
            if seen["worst_force"] is None or snap["total"] > seen["worst_force"]["total"]:
                seen["worst_force"] = snap
            if seen["worst_overlap"] is None or snap["deepest"] > seen["worst_overlap"]["deepest"]:
                seen["worst_overlap"] = snap

        r = run_trial(model, data, controller, after_step=after_step)
        drift = np.linalg.norm([s.drift_x, s.drift_y, s.drift_z])
        tumble = np.degrees(np.linalg.norm([s.tumble_x, s.tumble_y, s.tumble_z]))
        print(f"attempt {index}: {r.outcome.value}; drift {100 * drift:.0f} cm/s, tumble {tumble:.2f} deg/s, {r.duration:.0f} s long")
        show("first contact of any kind", seen["first_contact"])
        show("first time force passes 150 kN", seen["first_force"])
        show("first time overlap passes 1 cm", seen["first_overlap"])
        show("largest force", seen["worst_force"])
        show("deepest overlap", seen["worst_overlap"])


if __name__ == "__main__":
    main()
