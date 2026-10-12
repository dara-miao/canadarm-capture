"""Render a short preview of the simulation to docs/media/preview.mp4.

    python scripts/render_preview.py [--stills]
    python scripts/render_preview.py --vertical     # a 6.5-second portrait cut, preview_vertical.mp4

One continuous shot of a capture at four times real speed: the whole station with the
vehicle drifting beside it, in toward the end effector as it lines up, an x-ray view as
the pin enters and the snare closes, and back out to the whole station once the vehicle
is held. No captions.
Needs the 3D models (scripts/fetch_assets.py), the sky (scripts/make_sky.py), and ffmpeg.
--stills writes a few frames to docs/media/preview_*.png instead of the video.
"""

import subprocess
import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import scene  # noqa: E402
from capture.controller import CaptureController  # noqa: E402
from capture.trial import run_trial  # noqa: E402

OUT = ROOT / "docs" / "media"
WIDTH, HEIGHT, FPS = 1280, 720, 30
# Pacing: (seconds into the video, simulated seconds after the snare fires). The video
# plays the simulation between each pair at a steady rate.
PACE = [(0.0, -40.0), (17.6, 30.5)]  # four times real speed throughout
# The portrait cut is short, so it hurries through the approach and the pull-back and
# slows for the snare. A tall frame sees less to either side, so the camera stands further off.
PACE_VERTICAL = [(0.0, -40.0), (0.7, -35.0), (2.5, -3.0), (4.6, 12.0), (6.5, 30.5)]
STAND_OFF_VERTICAL = (2.0, 1.3)  # distance multipliers: whole-station shots, close shots
SKY_SPEED = 12.0  # times the real rate, so the stars visibly move

# Camera keys, timed from the moment the snare fires [s]: distance [m], azimuth and
# elevation [deg], how far above the end-effector mouth to look [m], how solid the end
# effector's shell is drawn (1 solid, less is see-through), and what the camera looks at
# (0 the middle of the whole station, 1 the end effector).
KEYS = [
    (-40.0, 120.0, 30.0, -22.0, 0.0, 1.0, 0.0),
    (-35.0, 105.0, 36.0, -20.0, 0.0, 1.0, 0.0),
    (-24.0, 15.0, 55.0, -8.0, 1.2, 1.0, 1.0),
    (-8.0, 4.2, 78.0, -4.0, 0.3, 1.0, 1.0),
    (-2.0, 2.4, 92.0, 4.0, -0.1, 0.22, 1.0),
    (14.0, 2.6, 118.0, 10.0, -0.1, 0.22, 1.0),
    (18.0, 5.0, 135.0, 14.0, 0.6, 1.0, 1.0),
    (27.0, 110.0, 165.0, 24.0, 0.0, 1.0, 0.0),
    (30.5, 122.0, 170.0, 26.0, 0.0, 1.0, 0.0),
]


def _ease(x: float) -> float:
    return x * x * (3 - 2 * x)


def camera_at(t: float) -> tuple[float, ...]:
    """Camera settings at time t after firing, eased between the keys either side."""
    if t <= KEYS[0][0]:
        return KEYS[0][1:]
    for a, b in zip(KEYS, KEYS[1:]):
        if t <= b[0]:
            u = _ease((t - a[0]) / (b[0] - a[0]))
            return tuple(x + u * (y - x) for x, y in zip(a[1:], b[1:]))
    return KEYS[-1][1:]


def sim_time_at(pace: list[tuple[float, float]], video_time: float) -> float:
    """Simulated time, after firing, shown at a moment in the video."""
    for (v0, s0), (v1, s1) in zip(pace, pace[1:]):
        if video_time <= v1:
            return s0 + (video_time - v0) / (v1 - v0) * (s1 - s0)
    return float("inf")


def main() -> None:
    stills = "--stills" in sys.argv
    vertical = "--vertical" in sys.argv
    width, height = (1080, 1920) if vertical else (WIDTH, HEIGHT)
    pace = PACE_VERTICAL if vertical else PACE
    name = "preview_vertical.mp4" if vertical else "preview.mp4"
    model = scene.build_model(moving_sky=True)
    model.vis.global_.offwidth, model.vis.global_.offheight = max(width, 1920), max(height, 1080)
    data = mujoco.MjData(model)
    # The end effector's shell, which fades for the x-ray view.
    lee = model.body("lee").id
    shell = [g for g in range(model.ngeom) if model.geom_bodyid[g] == lee and model.geom(g).name.startswith("mesh_")]

    def start() -> CaptureController:
        scene.reset(model, data, lateral=(0.08, -0.05), tilt=np.radians((6.0, -5.0)), roll=np.radians(8.0))
        scene.set_vehicle_velocity(model, data, drift=(0.012, -0.008, 0.008), tumble=np.radians((0.25, -0.3, 0.12)))
        return CaptureController(model)

    # A first pass without drawing, to learn when the snare fires.
    t_trigger = run_trial(model, data, start()).t_trigger
    controller = start()

    cam = mujoco.MjvCamera()
    frames_wanted = {0: "wide", 60: "approach", 200: "closing", 320: "xray", 470: "held", 525: "end"} if stills else None
    ffmpeg = None
    if not stills:
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(OUT / name)],
            stdin=subprocess.PIPE,
        )  # fmt: skip
    state = {"n": 0}

    with mujoco.Renderer(model, height=height, width=width) as renderer:

        def draw(d: mujoco.MjData) -> None:
            t = d.time - t_trigger
            if t < sim_time_at(pace, state["n"] / FPS):
                return
            distance, azimuth, elevation, lift, solid, focus = camera_at(t)
            if vertical:
                far, close = STAND_OFF_VERTICAL
                distance *= close + (1 - focus) * (far - close)
            scene.turn_sky(model, d, SKY_SPEED * scene.ORBIT_RATE * d.time)
            mujoco.mj_kinematics(model, d)
            model.geom_rgba[shell, 3] = solid
            mouth = d.site("lee_mouth")
            near = mouth.xpos + lift * mouth.xmat.reshape(3, 3)[:, 2]
            cam.lookat[:] = model.stat.center + focus * (near - model.stat.center)
            cam.distance, cam.azimuth, cam.elevation = distance, azimuth, elevation
            if stills and state["n"] not in frames_wanted:
                state["n"] += 1
                return
            renderer.update_scene(d, camera=cam)
            frame = renderer.render()
            if stills:
                Image.fromarray(frame).save(OUT / f"preview_{frames_wanted[state['n']]}.png")
            else:
                ffmpeg.stdin.write(frame.tobytes())
            state["n"] += 1

        result = run_trial(model, data, controller, on_step=draw)

    if ffmpeg:
        ffmpeg.stdin.close()
        ffmpeg.wait()
        path = OUT / name
        print("wrote", path.relative_to(ROOT), f"({path.stat().st_size / 1e6:.1f} MB, {state['n'] / FPS:.0f} s)")
    print("outcome:", result.outcome.value, "| snare fired at", round(t_trigger, 1), "s |", state["n"], "frames")


if __name__ == "__main__":
    main()
