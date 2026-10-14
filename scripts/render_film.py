"""Render the project's two films to docs/media/.

    python scripts/render_film.py capture      # a clean capture, no text: capture.mp4
    python scripts/render_film.py rim          # the rim failure and the fix, captioned: rim_contact.mp4
    python scripts/render_film.py shapes       # the capture with the collision-shape view, captioned, quick: capture_shapes.mp4
    python scripts/render_film.py rim --fast   # a quick low-resolution check
    python scripts/render_film.py rim --stills # a contact sheet instead of a film

Both films are the same real attempt: scenario 4 of the harsh pilot batch, a drifting,
tumbling Cygnus. "capture" shows it on the current model, with an x-ray view of the
snare closing and the fixture being pulled in. "rim" cross-fades to the collision
shapes the solver actually uses and shows the attempt twice from the moment the tilted
fixture plate meets the end effector's rim: first with the rim as the tops of the wall
boxes, where the solver fails and the vehicle is thrown off, then with the rim as a ring
of spheres, where it seats. The two runs are identical until that moment.

Rendered at 1920x1080 and 60 fps, and saved at 1280x720 so that each file stays under
about 10 MB, which is what GitHub will play in the browser. The camera moves on smooth
curves through its keys, and each frame blends several moments for a light motion blur. Needs the 3D models, the sky
(scripts/make_sky.py), and ffmpeg. --stills writes to $FILM_STILLS or results/, one frame
every $FILM_STILL_STEP seconds (default 2) within $FILM_STILL_RANGE ("from,to" seconds).
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from capture import batch, scene  # noqa: E402
from capture.controller import CaptureController  # noqa: E402
from capture.sensing import PinSensor, SensorConfig  # noqa: E402
from capture.trial import run_trial  # noqa: E402
from pilot_lost import HARSH  # noqa: E402

OUT = ROOT / "docs" / "media"
WIDTH, HEIGHT, FPS = 1920, 1080, 60
SAVE_WIDTH = 1280  # the saved file is scaled down to this width
SUPERSAMPLE = 1.25  # render larger and scale down, which steadies the star texture
SUBFRAMES = 4  # moments blended into each frame: motion blur, and it calms the stars
SKY_SPEED = 8.0  # times the real orbital rate
DRIFT = 2.0  # [deg/s] of camera azimuth, always, so the camera never stops
CAPTION_FONT = "/System/Library/Fonts/HelveticaNeue.ttc"  # face 7 is Light
READOUT_FONT = "/System/Library/Fonts/SFNSMono.ttf"
SCENARIO = 4  # of the harsh pilot batch, seed 0

# Runs the films can draw on: the rim built two ways.
RUNS = {"spheres": {}, "boxes": {"rim": "boxes"}}


@dataclass
class Film:
    name: str
    duration: float
    # (seconds into the film, run, simulated seconds after the snare fires). Consecutive
    # keys with the same run are one continuous take; a change of run is a cut.
    pace: list
    # Camera keys by seconds into the film: distance [m], azimuth, elevation [deg], lift above
    # the mouth along the approach axis [m], focus (0 the middle of the station, 1 the end
    # effector), and how far the camera turns to look at the end effector side-on.
    moves: list
    shell: list = field(default_factory=list)  # (t0, t1, from, to): end effector shell opacity
    shapes: list = field(default_factory=list)  # (t0, t1, from, to): models (0) to collision shapes (1)
    contacts: list = field(default_factory=list)  # (t0, t1, from, to): contact points drawn
    cuts: list = field(default_factory=list)  # (t0, t1): fade through black
    captions: list = field(default_factory=list)  # (t0, t1, text)
    readout: list = field(default_factory=list)  # (t0, t1): show the force and speed readout
    track: list = field(default_factory=list)  # (t0, t1, from, to): point of interest, the mouth (0) to the pin tip (1)
    subframes: int = SUBFRAMES  # moments blended into each frame


FILMS = {
    "capture": Film(
        name="capture",
        duration=24.0,
        pace=[
            (0.0, "spheres", -46.0), (2.5, "spheres", -38.0), (5.5, "spheres", -14.0), (9.0, "spheres", -1.0),
            (12.0, "spheres", 3.0), (19.0, "spheres", 21.0), (24.0, "spheres", 38.0),
        ],
        moves=[
            (0.0, 150.0, 10.0, -20.0, 0.0, 0.0, 0.0),  # the station
            (2.5, 120.0, 16.0, -18.0, 0.0, 0.1, 0.0),
            (5.5, 9.0, 40.0, -8.0, 0.8, 1.0, 0.0),  # push in to the arm and Cygnus
            (9.0, 3.6, 70.0, 0.0, 0.0, 1.0, 1.0),  # side-on as the arm closes in
            (12.0, 2.8, 90.0, 0.0, -0.1, 1.0, 1.0),
            (16.0, 2.8, 120.0, 0.0, -0.15, 1.0, 1.0),  # slow orbit while the fixture is pulled in
            (19.0, 3.2, 140.0, 0.0, -0.1, 1.0, 1.0),
            (20.5, 14.0, 146.0, 0.0, -0.1, 1.0, 1.0),  # straight back first, clear of the hull
            (22.0, 40.0, 155.0, -10.0, -3.0, 0.8, 0.3),
            (24.0, 150.0, 185.0, -22.0, 0.0, 0.5, 0.0),  # pull back out over Cygnus, the station beyond
        ],
        shell=[(8.5, 9.5, 1.0, 0.22), (19.5, 20.5, 0.22, 1.0)],
    ),
    "rim": Film(
        name="rim_contact",
        duration=52.0,
        pace=[
            (0.0, "spheres", -46.0), (3.0, "spheres", -36.0), (7.0, "spheres", -14.0), (11.0, "spheres", -1.0),
            (14.0, "spheres", 2.5), (15.0, "spheres", 3.5),
            # the box-top rim, slowed to a ninth of real speed around the moment the plate lands
            (15.0, "boxes", 3.5), (18.0, "boxes", 5.5), (21.5, "boxes", 6.9), (26.0, "boxes", 7.4), (31.0, "boxes", 12.0),
            # the same attempt again on the sphere rim, from before the plate lands
            (31.5, "spheres", 5.0), (34.0, "spheres", 6.9), (38.0, "spheres", 8.5), (44.0, "spheres", 20.0),
            (47.0, "spheres", 25.0), (52.0, "spheres", 38.0),
        ],
        moves=[
            (0.0, 150.0, 10.0, -20.0, 0.0, 0.0, 0.0),
            (3.0, 110.0, 18.0, -16.0, 0.0, 0.15, 0.0),
            (7.0, 9.0, 40.0, -8.0, 0.8, 1.0, 0.0),
            (11.0, 3.6, 70.0, 0.0, 0.0, 1.0, 1.0),
            (15.0, 2.8, 95.0, 0.0, -0.1, 1.0, 1.0),
            (21.5, 2.4, 115.0, 0.0, -0.15, 1.0, 1.0),  # close on the rim as the plate lands
            (26.0, 2.4, 125.0, 0.0, -0.15, 1.0, 1.0),
            (31.0, 12.0, 140.0, 0.0, 0.0, 1.0, 1.0),  # pull back as the vehicle flies off
            (31.5, 2.8, 95.0, 0.0, -0.1, 1.0, 1.0),  # the cut hides this jump
            (38.0, 2.4, 118.0, 0.0, -0.15, 1.0, 1.0),
            (44.0, 3.0, 140.0, 0.0, -0.1, 1.0, 1.0),
            (46.5, 14.0, 146.0, 0.0, -0.1, 1.0, 1.0),  # straight back first, clear of the hull
            (48.5, 40.0, 155.0, -10.0, -3.0, 0.8, 0.3),
            (52.0, 150.0, 185.0, -22.0, 0.0, 0.5, 0.0),
        ],
        shell=[(8.5, 9.5, 1.0, 0.22), (45.0, 46.0, 0.22, 1.0)],
        shapes=[(14.5, 15.5, 0.0, 1.0), (44.5, 45.5, 1.0, 0.0)],
        contacts=[(15.5, 16.0, 0.0, 1.0), (44.0, 44.5, 1.0, 0.0)],
        cuts=[(31.0, 32.0)],
        captions=[
            (1.0, 5.5, "Canadarm2 capturing a drifting Cygnus, simulated in MuJoCo"),
            (9.5, 14.0, "The snare closes on the grapple pin"),
            (16.0, 20.5, "What the engine actually collides: simple shapes, not the models"),
            (21.0, 25.0, "Here the rim is the tops of 16 overlapping boxes"),
            (26.5, 31.0, "The plate lands on a seam: 14,600 kN, and the vehicle is thrown off"),
            (33.0, 37.0, "The same attempt, with the rim as a ring of 32 spheres"),
            (40.0, 44.0, "The plate seats, pull-in levers it flat, the latches clamp"),
            (46.5, 51.5, "Harsh batch: 3 of 30 captured became 30 of 30. Nothing else changed."),
        ],
        readout=[(16.0, 31.0), (32.0, 44.0)],
        track=[(27.0, 31.0, 0.0, 0.55)],
    ),
    "shapes": Film(
        name="capture_shapes",
        duration=22.0,
        subframes=6,
        pace=[
            (0.0, "spheres", -46.0), (2.0, "spheres", -34.0), (5.0, "spheres", -8.0), (8.0, "spheres", 2.5),
            (9.5, "spheres", 5.0), (16.0, "spheres", 21.0), (22.0, "spheres", 38.0),
        ],
        moves=[
            (0.0, 150.0, 10.0, -20.0, 0.0, 0.0, 0.0),
            (2.0, 110.0, 18.0, -16.0, 0.0, 0.15, 0.0),
            (5.0, 9.0, 40.0, -8.0, 0.8, 1.0, 0.0),
            (8.0, 3.6, 70.0, 0.0, 0.0, 1.0, 1.0),
            (11.0, 2.8, 90.0, 0.0, -0.1, 1.0, 1.0),
            (16.0, 2.8, 125.0, 0.0, -0.15, 1.0, 1.0),
            (18.0, 14.0, 140.0, 0.0, -0.1, 1.0, 1.0),  # straight back first, clear of the hull
            (20.0, 40.0, 152.0, -10.0, -3.0, 0.8, 0.3),
            (22.0, 150.0, 185.0, -22.0, 0.0, 0.5, 0.0),
        ],
        shell=[(5.0, 6.0, 1.0, 0.22), (17.0, 18.0, 0.22, 1.0)],
        shapes=[(9.0, 10.0, 0.0, 1.0), (16.5, 17.5, 1.0, 0.0)],
        contacts=[(10.0, 10.5, 0.0, 1.0), (16.0, 16.5, 1.0, 0.0)],
        captions=[
            (0.6, 3.5, "Canadarm2 capturing a drifting Cygnus, simulated in MuJoCo"),
            (5.5, 8.5, "The snare closes on the grapple pin"),
            (10.2, 13.2, "The collision shapes the solver uses: the rim is a ring of spheres"),
            (13.2, 16.2, "The tilted plate seats, pull-in levers it flat, the latches clamp"),
        ],
        readout=[(10.5, 16.3)],
    ),
}


def _smooth(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def _pchip(xs: np.ndarray, ys: np.ndarray, x: float) -> float:
    """Smooth curve through the points, with no overshoot (monotone cubic Hermite)."""
    x = min(max(x, xs[0]), xs[-1])
    if len(xs) == 1:
        return float(ys[0])
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    k = min(int(np.searchsorted(xs, x, side="right")) - 1, len(xs) - 2)
    s = (x - xs[k]) / h[k]
    h00, h10, h01, h11 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s, -2 * s**3 + 3 * s**2, s**3 - s**2
    return h00 * ys[k] + h10 * h[k] * m[k] + h01 * ys[k + 1] + h11 * h[k] * m[k + 1]


def fade(schedule, video_time: float, start: float) -> float:
    value = start
    for t0, t1, v0, v1 in schedule:
        if video_time >= t0:
            value = v0 + _smooth((video_time - t0) / (t1 - t0)) * (v1 - v0)
    return value


def camera_at(film: Film, video_time: float) -> np.ndarray:
    keys = np.array(film.moves)
    out = np.array([_pchip(keys[:, 0], keys[:, c], video_time) for c in range(1, keys.shape[1])])
    out[0] = np.exp(_pchip(keys[:, 0], np.log(keys[:, 1]), video_time))  # zoom evenly in log distance
    out[1] += DRIFT * video_time
    return out


def takes(film: Film) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """The pace split into continuous takes: (run, video times, simulated times)."""
    out, block = [], []
    for key in film.pace:
        if block and key[1] != block[-1][1]:
            out.append(block)
            block = []
        block.append(key)
    out.append(block)
    return [(b[0][1], np.array([k[0] for k in b], float), np.array([k[2] for k in b], float)) for b in out]


def sim_time_at(film: Film, video_time: float) -> tuple[str, float]:
    """Which run, and how long after the snare fires, one moment of the film shows."""
    all_takes = takes(film)
    for run, vt, st in all_takes:
        if video_time <= vt[-1]:
            return run, _pchip(vt, st, video_time)
    run, vt, st = all_takes[-1]
    return run, float(st[-1])


def start(model: mujoco.MjModel, data: mujoco.MjData) -> CaptureController:
    s = batch.sample(60, HARSH, seed=0)[SCENARIO]
    scene.reset(model, data, lateral=(s.lateral_x, s.lateral_y), tilt=(s.tilt_x, s.tilt_y), roll=s.roll)
    scene.set_vehicle_velocity(model, data, drift=(s.drift_x, s.drift_y, s.drift_z), tumble=(s.tumble_x, s.tumble_y, s.tumble_z))
    sensor = PinSensor(model, SensorConfig(s.sensor_delay, s.sensor_rate, s.sensor_pos_noise, s.sensor_angle_noise), seed=s.seed)
    return CaptureController(model, sensor=sensor)


class Run:
    """One simulated attempt on one model, with the moments the film needs recorded."""

    def __init__(self, label: str, build: dict, size: tuple[int, int], fast: bool):
        self.label = label
        self.model = model = scene.build_model(moving_sky=True, sun=True, **build)
        model.vis.global_.offwidth, model.vis.global_.offheight = size
        model.vis.quality.offsamples = 4 if fast else 16  # antialiasing, so thin edges do not shimmer
        model.vis.map.znear = 0.001  # the default near clip cut away anything within 1.3 m of the camera
        model.vis.map.force = 0.025
        model.vis.scale.contactwidth, model.vis.scale.contactheight = 0.0018, 0.0004
        model.vis.rgba.contactpoint[:] = [0.2, 0.85, 1.0, 1.0]
        self.data = mujoco.MjData(model)
        self.plate = model.geom("gf_plate").id
        self.vehicle = model.body("vehicle").id
        # Which geoms are the detailed models, the collision shapes, and the end effector's shell.
        lee = model.body("lee").id
        names = [model.geom(g).name for g in range(model.ngeom)]
        mesh = np.array([n.startswith("mesh_") for n in names])
        self.shell = np.array([n.startswith("mesh_") and model.geom_bodyid[g] == lee for g, n in enumerate(names)])
        collide = np.array([bool(model.geom_contype[g] or model.geom_conaffinity[g]) and not mesh[g] for g in range(model.ngeom)])
        collide |= np.array([n.startswith(("v_", "hull_")) for n in names])
        self.wall_ids = np.flatnonzero([n.startswith("lee_wall_") for n in names])
        # Each render leaves the other view's shapes out entirely, so they neither draw nor
        # cast anything: group 1 is the detailed models, group 2 the hidden collision shapes.
        hidden = collide & (model.geom_rgba[:, 3] == 0)
        model.geom_group[mesh] = 1
        model.geom_group[hidden] = 2
        model.geom_group[[n.startswith("mesh_station") for n in names]] = 0  # scenery in both views
        model.geom_group[names.index("truss")] = 3  # the station's stand-in box: never drawn
        self.rgba = model.geom_rgba.copy()
        self.shape_rgba = self.rgba.copy()
        self.shape_rgba[hidden, 3] = 1.0
        self.frames: dict[int, tuple[float, np.ndarray]] = {}  # subframe index -> (time, qpos)
        self.trace = None  # rows of (time after firing, force on the plate, vehicle speed)
        self.renderer = None

    def record(self, wanted: list[tuple[int, float]]) -> None:
        """Run the attempt, keeping the state at each wanted (subframe index, time after firing)."""
        model, data = self.model, self.data
        t_trigger = run_trial(model, data, start(model, data)).t_trigger
        wanted = sorted(wanted, key=lambda w: w[1])
        at = 0
        f6, v6 = np.empty(6), np.empty(6)
        trace = []

        def on_step(d: mujoco.MjData) -> None:
            nonlocal at
            while at < len(wanted) and d.time - t_trigger >= wanted[at][1]:
                self.frames[wanted[at][0]] = (d.time, d.qpos.copy())
                at += 1

        def after_step(d: mujoco.MjData) -> None:
            force = 0.0
            for i in range(d.ncon):
                c = d.contact[i]
                if self.plate in (c.geom1, c.geom2):
                    mujoco.mj_contactForce(model, d, i, f6)
                    force += abs(f6[0])
            mujoco.mj_objectVelocity(model, d, mujoco.mjtObj.mjOBJ_BODY, self.vehicle, v6, 0)
            trace.append((d.time - t_trigger, force, float(np.linalg.norm(v6[3:]))))

        result = run_trial(model, data, start(model, data), on_step=on_step, after_step=after_step)
        self.t_trigger = t_trigger
        self.trace = np.array(trace)
        print(f"  {result.outcome.value}, snare fired at {t_trigger:.1f} s, {len(self.frames)} of {len(wanted)} moments kept")

    def measure(self, since: float) -> tuple[float, float]:
        """Force on the fixture plate [N] and the vehicle's speed [m/s] at a time after firing."""
        i = min(int(np.searchsorted(self.trace[:, 0], since)), len(self.trace) - 1)
        return float(self.trace[i, 1]), float(self.trace[i, 2])

    def draw(self, cam, option, colours: np.ndarray, contacts: bool, shapes_view: bool) -> np.ndarray:
        self.model.geom_rgba[:] = colours
        option.geomgroup[:] = 0
        option.geomgroup[0] = 1
        option.geomgroup[2 if shapes_view else 1] = 1
        option.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = contacts
        option.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = False  # the arrows jump in length; points only
        self.renderer.update_scene(self.data, camera=cam, scene_option=option)
        self.renderer.scene.flags[mujoco.mjtRndFlag.mjRND_CULL_FACE] = 0  # thin solar arrays show from both sides
        return self.renderer.render().astype(np.float32)

    def moment(self, film: Film, cam, option, index: int, video_time: float) -> np.ndarray:
        model, data = self.model, self.data
        time, qpos = self.frames[index]
        data.qpos[:] = qpos
        data.time = time
        scene.turn_sky(model, data, SKY_SPEED * scene.ORBIT_RATE * time)
        mujoco.mj_forward(model, data)
        distance, azimuth, elevation, lift, focus, square = camera_at(film, video_time)
        solid = fade(film.shell, video_time, 1.0)
        mix = fade(film.shapes, video_time, 0.0)
        contact = fade(film.contacts, video_time, 0.0)
        mouth = data.site("lee_mouth")
        axis = mouth.xmat.reshape(3, 3)[:, 2]
        track = fade(film.track, video_time, 0.0)
        near = mouth.xpos + lift * axis + track * (data.site("pin_tip").xpos - mouth.xpos)
        # The elevation at which the camera looks square to the end effector's axis.
        a = np.radians(azimuth)
        side = np.degrees(np.arctan2(-(np.cos(a) * axis[0] + np.sin(a) * axis[1]), axis[2]))
        side = (side + 90.0) % 180.0 - 90.0
        elevation = (1 - square) * elevation + square * side
        cam.lookat[:] = model.stat.center + focus * (near - model.stat.center)
        cam.distance, cam.azimuth, cam.elevation = distance, azimuth, elevation
        models = self.rgba.copy()
        models[self.shell, 3] = solid
        image = self.draw(cam, option, models, False, False) if mix < 0.999 else None
        if mix > 0.001:
            # A cutaway: the wall boxes on the camera's side of the tube are left out.
            az, el = np.radians(azimuth), np.radians(elevation)
            eye = cam.lookat - distance * np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
            shapes = self.shape_rgba.copy()
            toward = eye - mouth.xpos
            toward -= (toward @ axis) * axis
            for g in self.wall_ids:
                out = data.geom_xpos[g] - mouth.xpos
                out -= (out @ axis) * axis
                facing = out @ toward / (np.linalg.norm(out) * np.linalg.norm(toward) + 1e-9)
                shapes[g, 3] = 1.0 - _smooth(facing / 0.5)  # fade, so boxes never pop
            other = self.draw(cam, option, shapes, False, True)
            if contact > 0.001:
                other = (1 - contact) * other + contact * self.draw(cam, option, shapes, True, True)
            image = other if image is None else (1 - mix) * image + mix * other
        return image


def overlay(frame: Image.Image, film: Film, run: Run, video_time: float, since: float, fonts) -> Image.Image:
    """Captions, the readout, and the fades through black."""
    width, height = frame.size
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    caption_font, readout_font = fonts

    def alpha_in(t0: float, t1: float, ramp: float = 0.4) -> float:
        if not t0 <= video_time <= t1:
            return 0.0
        return min(1.0, (video_time - t0) / ramp, (t1 - video_time) / ramp)

    for t0, t1, text in film.captions:
        a = alpha_in(t0, t1)
        if a <= 0:
            continue
        w = draw.textlength(text, font=caption_font)
        x, y = (width - w) / 2, height * 0.885
        draw.text((x + 2, y + 2), text, font=caption_font, fill=(0, 0, 0, int(160 * a)))
        draw.text((x, y), text, font=caption_font, fill=(255, 255, 255, int(255 * a)))

    for t0, t1 in film.readout:
        a = alpha_in(t0, t1)
        if a <= 0:
            continue
        force, speed = run.measure(np.floor(since * 10) / 10)  # held for a tenth of a second, so it can be read
        lines = [
            f"rim as {'box tops' if run.label == 'boxes' else 'spheres'}",
            f"force on the fixture plate {force / 1e3:>9,.1f} kN",
            f"vehicle speed {speed * 100:>5.1f} cm/s",
        ]
        x, y = width * 0.03, height * 0.05
        for i, line in enumerate(lines):
            yy = y + i * readout_font.size * 1.5
            draw.text((x + 2, yy + 2), line, font=readout_font, fill=(0, 0, 0, int(160 * a)))
            draw.text((x, yy), line, font=readout_font, fill=(255, 255, 255, int(235 * a)))

    out = Image.alpha_composite(frame.convert("RGBA"), layer).convert("RGB")
    for t0, t1 in film.cuts:
        if t0 <= video_time <= t1:
            mid, half = (t0 + t1) / 2, (t1 - t0) / 2
            keep = min(1.0, abs(video_time - mid) / half)
            out = Image.eval(out, lambda v, k=keep: int(v * k))
    return out


def main() -> None:
    which = next((a for a in sys.argv[1:] if a in FILMS), None)
    if which is None:
        sys.exit(f"usage: render_film.py {{{'|'.join(FILMS)}}} [--fast] [--stills]")
    film = FILMS[which]
    fast, stills = "--fast" in sys.argv, "--stills" in sys.argv
    width, height, fps, subframes, supersample = (640, 360, 30, 1, 1.0) if fast else (WIDTH, HEIGHT, FPS, film.subframes, SUPERSAMPLE)
    big = (round(width * supersample), round(height * supersample))
    out = OUT / f"{film.name}{'_fast' if fast else ''}.mp4"

    # Every subframe the film needs, by run.
    rate = fps * subframes
    n = int(film.duration * rate)
    wanted: dict[str, list[tuple[int, float]]] = {name: [] for name in RUNS}
    moments = []
    for i in range(n):
        run_name, since = sim_time_at(film, i / rate)
        wanted[run_name].append((i, since))
        moments.append((run_name, since))

    runs: dict[str, Run] = {}
    for name, build in RUNS.items():
        if not wanted[name]:
            continue
        print(f"run: rim as {name}")
        runs[name] = Run(name, build, big, fast)
        runs[name].record(wanted[name])

    fonts = (
        ImageFont.truetype(CAPTION_FONT, round(height * 0.038), index=7),
        ImageFont.truetype(READOUT_FONT, round(height * 0.026)),
    )
    ffmpeg = None
    if not stills:
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
             "-r", str(fps), "-i", "-", "-vf", f"scale={SAVE_WIDTH}:-2:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
             "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
            stdin=subprocess.PIPE,
        )  # fmt: skip
    cam = mujoco.MjvCamera()
    option = mujoco.MjvOption()
    sheet = []
    for run in runs.values():
        run.renderer = mujoco.Renderer(run.model, height=big[1], width=big[0])
    still_step = round(fps * float(os.environ.get("FILM_STILL_STEP", 2.0)))
    still_range = [float(v) for v in os.environ.get("FILM_STILL_RANGE", f"0,{film.duration}").split(",")]
    try:
        frames = n // subframes
        for f in range(frames):
            if stills and (f % still_step or not still_range[0] <= f / fps <= still_range[1]):
                continue
            image = None
            for k in range(subframes):
                i = f * subframes + k
                run_name, since = moments[i]
                run = runs[run_name]
                if i not in run.frames:  # past the end of the attempt: hold its last moment
                    run.frames[i] = run.frames[max(run.frames)]
                part = run.moment(film, cam, option, i, i / rate)
                image = part if image is None else image + part
            frame = np.clip(image / subframes, 0, 255).astype(np.uint8)
            frame = Image.fromarray(frame).resize((width, height), Image.LANCZOS)
            run_name, since = moments[f * subframes]
            frame = overlay(frame, film, runs[run_name], f / fps, since, fonts)
            if stills:
                sheet.append(np.array(frame.resize((640, 360))))
            else:
                ffmpeg.stdin.write(np.asarray(frame).tobytes())
            if f % (fps * 5) == 0:
                print(f"  frame {f} / {frames}", flush=True)
    finally:
        for run in runs.values():
            run.renderer.close()

    if stills:
        rows = [np.hstack(sheet[k : k + 4] + [np.zeros_like(sheet[0])] * (4 - len(sheet[k : k + 4]))) for k in range(0, len(sheet), 4)]
        path = Path(os.environ.get("FILM_STILLS", ROOT / "results")) / f"{film.name}_sheet.png"
        Image.fromarray(np.vstack(rows)).save(path)
        print("wrote", path)
    else:
        ffmpeg.stdin.close()
        ffmpeg.wait()
        print("wrote", out.relative_to(ROOT), f"({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
