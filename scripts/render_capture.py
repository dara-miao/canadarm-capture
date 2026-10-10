"""Render the grapple sequence (close, centre, pull in) to docs/media/."""

import sys
from pathlib import Path

import mujoco
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import scene, snare  # noqa: E402

OUT = ROOT / "docs" / "media"
FPS = 10
DURATION = snare.SEQUENCE_TIME + 1.5
STILLS = {"snare_open": 0.0, "snare_closed": snare.CLOSE_TIME + 1.0, "snare_seated": snare.SEQUENCE_TIME + 1.0}


def main() -> None:
    model = scene.build_model()
    data = mujoco.MjData(model)
    # Start 6 cm off-centre so the centring action is visible.
    scene.reset(model, data, standoff=-0.28, lateral=(0.06, 0.0))

    cam = mujoco.MjvCamera()
    cam.lookat[:] = data.site("lee_mouth").xpos - [0, 0, 0.12]
    cam.distance, cam.azimuth, cam.elevation = 1.5, 90.0, -12.0

    dt = model.opt.timestep
    every = int(round(1 / FPS / dt))
    still_steps = {int(round(t / dt)): name for name, t in STILLS.items()}
    frames = []
    OUT.mkdir(parents=True, exist_ok=True)
    with mujoco.Renderer(model, height=540, width=960) as renderer:
        for i in range(int(round(DURATION / dt)) + 1):
            if i % every == 0 or i in still_steps:
                renderer.update_scene(data, camera=cam)
                img = Image.fromarray(renderer.render())
                if i % every == 0:
                    frames.append(img.resize((640, 360)))
                if i in still_steps:
                    img.save(OUT / f"{still_steps[i]}.png")
                    print("wrote", f"docs/media/{still_steps[i]}.png")
            scene.set_snare(model, data, *snare.grapple_command(i * dt))
            mujoco.mj_step(model, data)

    gif = OUT / "snare_capture.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, optimize=True)
    print("wrote", gif.relative_to(ROOT), f"({gif.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
