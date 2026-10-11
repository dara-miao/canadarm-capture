"""Watch a capture in MuJoCo's interactive viewer. The attempt repeats until the window closes.

On macOS run it with mjpython:

    .venv/bin/mjpython scripts/view.py [--speed 4]

Drag with the mouse to orbit, scroll to zoom, double-click a body to select it,
and press space to pause.
"""

import argparse
import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import scene  # noqa: E402
from capture.controller import CaptureController, Phase  # noqa: E402

FRAME_TIME = 1 / 60


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--speed", type=float, default=4.0, help="playback speed relative to real time")
    parser.add_argument("--shapes", action="store_true", help="show the collision shapes instead of the 3D models")
    args = parser.parse_args()

    model = scene.build_model(meshes=not args.shapes)
    data = mujoco.MjData(model)
    controller = CaptureController(model)
    steps_per_frame = max(1, int(round(args.speed * FRAME_TIME / model.opt.timestep)))

    with mujoco.viewer.launch_passive(model, data) as viewer:
        scene.reset(model, data)
        viewer.cam.lookat[:] = data.site("lee_mouth").xpos + [0, 0, 1.2]
        viewer.cam.distance, viewer.cam.azimuth, viewer.cam.elevation = 10.0, 60.0, -8.0

        while viewer.is_running():
            scene.reset(model, data, lateral=(0.09, -0.05), tilt=np.radians((5.0, -4.0)))
            scene.set_vehicle_velocity(model, data, drift=(0.006, -0.004, 0.004), tumble=np.radians((0.08, -0.1, 0.04)))
            controller.reset(data)
            hold_until = None  # keep showing the result for a few seconds
            while viewer.is_running() and (hold_until is None or data.time < hold_until):
                start = time.perf_counter()
                for _ in range(steps_per_frame):
                    mujoco.mj_step1(model, data)
                    data.qfrc_applied[:] = 0  # the controller re-adds its latch force every step
                    controller.step(data)
                    mujoco.mj_step2(model, data)
                if controller.phase is Phase.DONE and hold_until is None:
                    hold_until = data.time + 8.0
                viewer.sync()
                time.sleep(max(0.0, FRAME_TIME - (time.perf_counter() - start)))


if __name__ == "__main__":
    main()
