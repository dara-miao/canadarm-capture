"""Record the force between the fixture and the end effector's rim, step by step, for one
attempt on the old rim and on the fixed one.

    python experiments/trace_rim_force.py

The attempt is scenario 4 of the harsh pilot batch, the one the regression test replays.
Writes docs/data/rim_force_trace.csv: seconds after the snare fires, and the total contact
force on the vehicle from everything except the snare bars, for each rim.
"""

import csv
import sys
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from capture import batch, scene  # noqa: E402
from capture.controller import CaptureController  # noqa: E402
from capture.sensing import PinSensor, SensorConfig  # noqa: E402
from capture.trial import run_trial  # noqa: E402
from pilot_lost import HARSH  # noqa: E402

WINDOW = (6.0, 10.0)  # [s] after firing


def trace(rim: str) -> tuple[list[tuple[float, float, float]], str]:
    s = batch.sample(60, HARSH, seed=0)[4]
    model = scene.build_model(meshes=False, rim=rim)
    data = mujoco.MjData(model)
    scene.reset(model, data, lateral=(s.lateral_x, s.lateral_y), tilt=(s.tilt_x, s.tilt_y), roll=s.roll)
    scene.set_vehicle_velocity(model, data, drift=(s.drift_x, s.drift_y, s.drift_z), tumble=(s.tumble_x, s.tumble_y, s.tumble_z))
    sensor = PinSensor(model, SensorConfig(s.sensor_delay, s.sensor_rate, s.sensor_pos_noise, s.sensor_angle_noise), seed=s.seed)
    controller = CaptureController(model, sensor=sensor)
    vehicle = model.body("vehicle").id
    vehicle_bodies = {vehicle, model.body("fixture").id}
    bars = {model.body(f"snare_{i}").id for i in range(3)}
    rows, f, v = [], np.empty(6), np.empty(6)

    def after_step(d: mujoco.MjData) -> None:
        if controller.t_trigger is None:
            return
        t = d.time - controller.t_trigger
        if not WINDOW[0] <= t <= WINDOW[1]:
            return
        total = 0.0
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = model.geom_bodyid[c.geom1], model.geom_bodyid[c.geom2]
            if (b1 in vehicle_bodies) != (b2 in vehicle_bodies) and b1 not in bars and b2 not in bars:
                mujoco.mj_contactForce(model, d, i, f)
                total += abs(f[0])
        mujoco.mj_objectVelocity(model, d, mujoco.mjtObj.mjOBJ_BODY, vehicle, v, 0)
        rows.append((round(t, 3), total, float(np.linalg.norm(v[3:]))))

    result = run_trial(model, data, controller, after_step=after_step)
    return rows, result.outcome.value


def main() -> None:
    boxes, outcome_boxes = trace("boxes")
    spheres, outcome_spheres = trace("spheres")
    path = ROOT / "docs" / "data" / "rim_force_trace.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seconds_after_firing", "force_box_top_rim_N", "vehicle_speed_box_top_rim_m_s", "force_sphere_rim_N", "vehicle_speed_sphere_rim_m_s"])
        for (t, fb, vb), (_, fs, vs) in zip(boxes, spheres):
            writer.writerow([t, round(fb, 1), round(vb, 4), round(fs, 1), round(vs, 4)])
    print("box-top rim:", outcome_boxes, "| sphere rim:", outcome_spheres)
    print("wrote", path.relative_to(ROOT), len(boxes), "rows")


if __name__ == "__main__":
    main()
