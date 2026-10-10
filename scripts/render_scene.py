"""Render still images of the capture scene to docs/media/."""

import sys
from pathlib import Path

import mujoco
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import scene  # noqa: E402

OUT = ROOT / "docs" / "media"

VIEWS = {
    # name: (lookat, distance, azimuth, elevation)
    "scene_wide": ((0.5, 1.0, 6.5), 30.0, 35.0, -12.0),
    "scene_closeup": (None, 6.0, 60.0, -10.0),
}


def main() -> None:
    model = scene.build_model()
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=0.6)

    OUT.mkdir(parents=True, exist_ok=True)
    with mujoco.Renderer(model, height=1080, width=1920) as renderer:
        for name, (lookat, distance, azimuth, elevation) in VIEWS.items():
            cam = mujoco.MjvCamera()
            cam.lookat[:] = data.site("lee_mouth").xpos if lookat is None else lookat
            cam.distance, cam.azimuth, cam.elevation = distance, azimuth, elevation
            renderer.update_scene(data, camera=cam)
            path = OUT / f"{name}.png"
            Image.fromarray(renderer.render()).save(path)
            print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
