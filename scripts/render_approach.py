"""Render a full approach and capture to docs/media/approach_capture.gif."""

import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import scene  # noqa: E402
from capture.controller import CaptureController  # noqa: E402
from capture.trial import run_trial  # noqa: E402

OUT = ROOT / "docs" / "media"
SIM_SECONDS_PER_FRAME = 0.6
PLAYBACK_FPS = 10  # 6x real time


def main() -> None:
    model = scene.build_model()
    data = mujoco.MjData(model)
    # Exaggerated start so the alignment is easy to see.
    scene.reset(model, data, lateral=(0.09, -0.05), tilt=np.radians((5.0, -4.0)))
    scene.set_vehicle_velocity(model, data, drift=(0.006, -0.004, 0.004), tumble=np.radians((0.08, -0.1, 0.04)))
    controller = CaptureController(model)

    cam = mujoco.MjvCamera()
    cam.lookat[:] = data.site("lee_mouth").xpos + [0, 0, 1.2]
    cam.distance, cam.azimuth, cam.elevation = 10.0, 60.0, -8.0

    frames = []
    next_frame = [0.0]
    with mujoco.Renderer(model, height=360, width=640) as renderer:

        def capture_frame(d: mujoco.MjData) -> None:
            if d.time < next_frame[0]:
                return
            next_frame[0] += SIM_SECONDS_PER_FRAME
            renderer.update_scene(d, camera=cam)
            img = Image.fromarray(renderer.render())
            ImageDraw.Draw(img).text((12, 10), f"{controller.phase.value.upper()}   t = {d.time:4.1f} s", fill=(255, 255, 255))
            frames.append(img)

        result = run_trial(model, data, controller, on_step=capture_frame)

    OUT.mkdir(parents=True, exist_ok=True)
    gif = OUT / "approach_capture.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=1000 // PLAYBACK_FPS, loop=0, optimize=True)
    print("success:", result.success, "| trigger at", round(result.t_trigger, 1), "s")
    print("wrote", gif.relative_to(ROOT), f"({gif.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")
    for name, idx in {"approach_start": 0, "approach_done": -1}.items():
        frames[idx].save(OUT / f"{name}.png")


if __name__ == "__main__":
    main()
