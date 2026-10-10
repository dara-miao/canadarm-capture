"""Diagnostic: when a snared pin is lost, what do the snare bars and their drive do?

Replays a few of the harsh scenarios from pilot_lost.py at two snare drive force limits
and prints, for the time after the snare has closed: how far the bars were pushed back,
how far apart the three bars got from each other, and the largest drive force.

    python experiments/replay_lost.py 0,4,5,6

Prints only. Single process, about 25 s per attempt.
"""

import sys
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from capture import batch, scene, snare  # noqa: E402
from capture.controller import CaptureController, ControllerConfig  # noqa: E402
from capture.sensing import PinSensor, SensorConfig  # noqa: E402
from capture.trial import run_trial  # noqa: E402
from pilot_lost import HARSH  # noqa: E402


def main() -> None:
    base = batch.sample(60, HARSH, seed=0)
    chosen = [int(i) for i in sys.argv[1].split(",")] if len(sys.argv) > 1 else [0, 4, 5, 6]
    for force in (1500.0, 3000.0):
        model = scene.build_model(meshes=False, snare_force=force)
        bars = [model.joint(f"snare_{i}").qposadr[0] for i in range(3)]
        drive = model.actuator("a_snare").id
        for i in chosen:
            s = base[i]
            data = mujoco.MjData(model)
            scene.reset(model, data, lateral=(s.lateral_x, s.lateral_y), tilt=(s.tilt_x, s.tilt_y), roll=s.roll)
            scene.set_vehicle_velocity(
                model, data, drift=(s.drift_x, s.drift_y, s.drift_z), tumble=(s.tumble_x, s.tumble_y, s.tumble_z)
            )
            sensor = PinSensor(
                model,
                SensorConfig(s.sensor_delay, s.sensor_rate, s.sensor_pos_noise, s.sensor_angle_noise),
                seed=s.seed,
            )
            controller = CaptureController(model, ControllerConfig(), sensor=sensor)
            log = []

            def on_step(d, controller=controller, log=log):
                if controller.t_trigger is not None and d.time - controller.t_trigger > snare.CLOSE_TIME:
                    log.append((d.time - controller.t_trigger, *d.qpos[bars], d.actuator_force[drive]))

            r = run_trial(model, data, controller, on_step=on_step)
            if not log:
                print(f"drive {force:.0f} N  scenario {i}: {r.outcome.value}, snare never closed")
                continue
            rows = np.array(log)
            q = rows[:, 1:4]  # bar positions [m]; 0 is fully open, 0.08 fully closed
            k = int(np.argmin(q.min(axis=1)))
            print(
                f"drive {force:.0f} N  scenario {i}: {r.outcome.value}, "
                f"speed at close {100 * r.close_speed:.1f} cm/s, "
                f"bars at close {q[0, 0]:.3f} m, furthest back {q.min():.3f} m at {rows[k, 0]:.1f} s after firing, "
                f"largest gap between bars {np.ptp(q, axis=1).max():.3f} m, "
                f"peak drive force {np.abs(rows[:, 4]).max():.0f} N"
            )


if __name__ == "__main__":
    main()
