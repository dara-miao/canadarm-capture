"""Pilot: what loads the snare after it closes, and does the vehicle's momentum explain it?

Reruns the harsh batch from pilot_lost.py, with the arm's default behaviour and with the
arm going limp as soon as the snare closes, and logs each attempt from the moment the
snare fires: the vehicle's motion relative to the station, the contact force the snare
bars put on the pin, the contact force between the vehicle and the rest of the end
effector, and when the pin left.

    python experiments/pilot_load.py

Writes docs/data/pilot_load.csv, one row per attempt in which the snare fired.
A pilot: 60 scenarios, one seed. About 5 minutes on 8 cores.
"""

import csv
import multiprocessing as mp
import os
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
from capture.trial import HELD_DEPTH, run_trial  # noqa: E402
from pilot_lost import HARSH  # noqa: E402

VARIANTS = {
    "baseline": {},
    "arm limp as soon as snare closes": {"limp_from_snare_close": True},
}
VEHICLE_MASS = 7000.0  # [kg], approximate; the fixture's 12.5 kg is left out


def _stage(since: float) -> str:
    """Which part of the grapple sequence a time after firing falls in."""
    if since < snare.CLOSE_TIME:
        return "closing"
    if since < snare.CLOSE_TIME + snare.SETTLE_TIME:
        return "pause"
    if since < snare.PULL_IN_END:
        return "pull-in"
    return "after pull-in"


def run(args: tuple[int, batch.Scenario, str]) -> dict | None:
    index, s, variant = args
    model = scene.build_model(meshes=False)
    data = mujoco.MjData(model)
    scene.reset(model, data, lateral=(s.lateral_x, s.lateral_y), tilt=(s.tilt_x, s.tilt_y), roll=s.roll)
    scene.set_vehicle_velocity(
        model, data, drift=(s.drift_x, s.drift_y, s.drift_z), tumble=(s.tumble_x, s.tumble_y, s.tumble_z)
    )
    sensor = PinSensor(
        model, SensorConfig(s.sensor_delay, s.sensor_rate, s.sensor_pos_noise, s.sensor_angle_noise), seed=s.seed
    )
    controller = CaptureController(model, ControllerConfig(**VARIANTS[variant]), sensor=sensor)

    vehicle = model.body("vehicle").id
    vehicle_bodies = {vehicle, model.body("fixture").id}
    bar_bodies = {model.body(f"snare_{i}").id for i in range(3)}
    bar_q = [model.joint(f"snare_{i}").qposadr[0] for i in range(3)]
    carriage = model.actuator("a_carriage").id
    dt = model.opt.timestep
    log = []  # since, bar force (3, mouth frame), wall force size, vehicle v (3), vehicle w size, depth, min bar, carriage force, tilt

    def after_step(d: mujoco.MjData) -> None:
        if controller.t_trigger is None:
            return
        R = d.site("lee_mouth").xmat.reshape(3, 3)
        bars, wall = np.zeros(3), np.zeros(3)
        f = np.empty(6)
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = model.geom_bodyid[c.geom1], model.geom_bodyid[c.geom2]
            if (b1 in vehicle_bodies) == (b2 in vehicle_bodies):
                continue
            mujoco.mj_contactForce(model, d, i, f)
            on_geom2 = c.frame.reshape(3, 3).T @ f[:3]  # world frame
            on_vehicle = on_geom2 if b2 in vehicle_bodies else -on_geom2
            if (b1 in bar_bodies) or (b2 in bar_bodies):
                bars += on_vehicle
            else:
                wall += on_vehicle
        v = np.empty(6)
        mujoco.mj_objectVelocity(model, d, mujoco.mjtObj.mjOBJ_BODY, vehicle, v, 0)  # at the centre of mass
        depth = -scene.pin_offset(model, d)[2]
        log.append((d.time - controller.t_trigger, *(R.T @ bars), np.linalg.norm(wall), *(R.T @ v[3:]),
                    np.linalg.norm(v[:3]), depth, d.qpos[bar_q].min(), d.actuator_force[carriage], scene.pin_axis_error(model, d)))  # fmt: skip

    r = run_trial(model, data, controller, after_step=after_step)
    if not log:
        return None
    L = np.array(log)
    since, bar, wall, v, w = L[:, 0], L[:, 1:4], L[:, 4], L[:, 5:8], L[:, 8]
    depth, bar_min, pull, tilt = L[:, 9], L[:, 10], L[:, 11], np.degrees(L[:, 12])
    bar_size = np.linalg.norm(bar, axis=1)
    closed = int(np.searchsorted(since, snare.CLOSE_TIME))
    closed = min(closed, len(since) - 1)
    gone = np.flatnonzero((since > snare.CLOSE_TIME) & (depth < HELD_DEPTH))
    end = int(gone[0]) if len(gone) else len(since) - 1  # the step the pin left, or the last step
    held = slice(closed, end + 1)
    k_bar = closed + int(np.argmax(bar_size[held]))
    k_wall = closed + int(np.argmax(wall[held]))
    speed = np.linalg.norm(v, axis=1)
    # the first step on which the rest of the end effector pushed on the vehicle with more than 10 kN
    hard = closed + int(np.argmax(wall[held] > 1e4)) if wall[held].max() > 1e4 else None
    before = slice(closed, (hard if hard is not None else end) + 1)  # from closure until then
    return {
        "scenario": index,
        "variant": variant,
        "outcome": r.outcome.value,
        "engaged": int(r.engaged),
        "close_speed_cm_s": round(100 * r.close_speed, 2),  # pin relative to the end effector
        # the vehicle's centre of mass relative to the station when the snare finished closing
        "vehicle_speed_at_close_cm_s": round(100 * speed[closed], 2),
        "vehicle_speed_out_at_close_cm_s": round(100 * v[closed, 2], 2),  # along the approach axis, + is away
        "vehicle_spin_at_close_deg_s": round(float(np.degrees(w[closed])), 3),
        "momentum_at_close_N_s": round(VEHICLE_MASS * speed[closed], 1),
        "left_at_s": "" if not len(gone) else round(float(since[end]), 2),
        "left_during": "" if not len(gone) else _stage(since[end]),
        "vehicle_speed_at_end_cm_s": round(100 * speed[end], 2),  # when the pin left, or when the attempt ended
        "vehicle_spin_at_end_deg_s": round(float(np.degrees(w[end])), 3),
        "tilt_at_close_deg": round(float(tilt[closed]), 2),  # pin axis against the end effector's axis
        "peak_tilt_deg": round(float(tilt[held].max()), 2),
        "peak_bar_force_N": round(float(bar_size[k_bar])),
        "peak_bar_force_at_s": round(float(since[k_bar]), 2),
        "peak_bar_force_during": _stage(since[k_bar]),
        "peak_bar_force_outward_N": round(float(-bar[held, 2].min())),  # holding the vehicle in
        "bar_impulse_N_s": round(float(bar_size[held].sum() * dt), 1),
        "peak_wall_force_N": round(float(wall[k_wall])),
        "peak_wall_force_at_s": round(float(since[k_wall]), 2),
        "tilt_at_peak_wall_force_deg": round(float(tilt[k_wall]), 2),
        "wall_10kN_at_s": "" if hard is None else round(float(since[hard]), 2),
        "tilt_at_wall_10kN_deg": "" if hard is None else round(float(tilt[hard]), 2),
        "vehicle_speed_at_wall_10kN_cm_s": "" if hard is None else round(100 * speed[hard], 2),
        "vehicle_spin_at_wall_10kN_deg_s": "" if hard is None else round(float(np.degrees(w[hard])), 3),
        "peak_bar_force_before_wall_10kN_N": round(float(bar_size[before].max())),
        "wall_impulse_N_s": round(float(wall[held].sum() * dt), 1),
        "peak_pull_in_force_N": round(float(np.abs(pull[held]).max())),
        "bars_furthest_back_m": round(float(bar_min[held].min()), 4),
    }


def main() -> None:
    base = batch.sample(60, HARSH, seed=0)
    jobs = [(i, s, name) for name in VARIANTS for i, s in enumerate(base)]
    workers = max(1, (os.cpu_count() or 2) - 2)
    with mp.get_context("spawn").Pool(workers) as pool:
        rows = [r for r in pool.map(run, jobs, chunksize=1) if r is not None]
    path = ROOT / "docs" / "data" / "pilot_load.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("wrote", path.relative_to(ROOT), len(rows), "rows")


if __name__ == "__main__":
    main()
