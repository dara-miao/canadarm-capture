"""Run many capture attempts and tabulate how they ended.

    python -m capture.batch --n 200 --seed 0 --out results/baseline.csv

A Scenario is everything that defines one attempt: how the vehicle starts, and
what the controller can sense. Scenarios are plain data, so a batch is
reproducible from its seed and can be spread over processes.
"""

import argparse
import csv
import multiprocessing as mp
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

import mujoco
import numpy as np

from . import scene
from .audit import Audit
from .controller import CaptureController, ControllerConfig
from .sensing import PinSensor, SensorConfig
from .trial import Outcome, run_trial


@dataclass
class Scenario:
    """One attempt. Offsets and velocities are in the end-effector mouth frame at the start."""

    seed: int = 0
    lateral_x: float = 0.0  # pin offset from the approach axis [m]
    lateral_y: float = 0.0
    tilt_x: float = 0.0  # pin axis tilt [rad]
    tilt_y: float = 0.0
    roll: float = 0.0  # vehicle rotation about its pin axis [rad]
    drift_x: float = 0.0  # vehicle centre-of-mass velocity [m/s]
    drift_y: float = 0.0
    drift_z: float = 0.0
    tumble_x: float = 0.0  # vehicle angular velocity [rad/s]
    tumble_y: float = 0.0
    tumble_z: float = 0.0
    sensor_delay: float = 0.0  # [s]
    sensor_rate: float = 0.0  # [Hz]; 0 means every simulation step
    sensor_pos_noise: float = 0.0  # [m]
    sensor_angle_noise: float = 0.0  # [rad]


@dataclass
class Ranges:
    """Limits for random scenarios. Each quantity is drawn uniformly inside its limit.

    Defaults for offset, tilt, and roll follow the worst case Canadarm2's end effector
    was tested at (Walker and Vandersluis, 1995). The drift default is the Shuttle end
    effector's capture velocity requirement (Daniell and Sachdev, 1982): a mechanism
    requirement, not a verified limit on a visiting vehicle. The tumble limit is not sourced.
    """

    lateral: float = 0.10  # [m], radius of a disc
    tilt: float = np.radians(15.0)  # [rad], radius of a disc
    roll: float = np.radians(10.0)  # [rad], plus or minus
    drift: float = 0.031  # [m/s], radius of a ball
    tumble: float = np.radians(0.5)  # [rad/s], radius of a ball
    sensor_delay: float = 0.0
    sensor_rate: float = 0.0
    sensor_pos_noise: float = 0.0
    sensor_angle_noise: float = 0.0


def _in_ball(rng: np.random.Generator, dim: int, radius: float) -> np.ndarray:
    """A point drawn uniformly from a disc (dim 2) or ball (dim 3)."""
    direction = rng.normal(size=dim)
    direction /= np.linalg.norm(direction)
    return direction * radius * rng.uniform() ** (1.0 / dim)


def sample(n: int, ranges: Ranges | None = None, seed: int = 0) -> list[Scenario]:
    ranges = ranges or Ranges()
    rng = np.random.default_rng(seed)
    scenarios = []
    for i in range(n):
        lateral, tilt = _in_ball(rng, 2, ranges.lateral), _in_ball(rng, 2, ranges.tilt)
        drift, tumble = _in_ball(rng, 3, ranges.drift), _in_ball(rng, 3, ranges.tumble)
        scenarios.append(
            Scenario(
                seed=seed * 1_000_003 + i,
                lateral_x=lateral[0], lateral_y=lateral[1],
                tilt_x=tilt[0], tilt_y=tilt[1], roll=rng.uniform(-ranges.roll, ranges.roll),
                drift_x=drift[0], drift_y=drift[1], drift_z=drift[2],
                tumble_x=tumble[0], tumble_y=tumble[1], tumble_z=tumble[2],
                sensor_delay=ranges.sensor_delay, sensor_rate=ranges.sensor_rate,
                sensor_pos_noise=ranges.sensor_pos_noise, sensor_angle_noise=ranges.sensor_angle_noise,
            )
        )  # fmt: skip
    return scenarios


# Vector quantities whose size can be swept while each scenario keeps its direction.
_VECTORS = {
    "lateral": ("lateral_x", "lateral_y"),
    "tilt": ("tilt_x", "tilt_y"),
    "drift": ("drift_x", "drift_y", "drift_z"),
    "tumble": ("tumble_x", "tumble_y", "tumble_z"),
}


def with_value(s: Scenario, quantity: str, value: float) -> Scenario:
    """A copy of a scenario with one quantity changed and everything else, including the seed, kept.

    For "lateral", "tilt", "drift", or "tumble" the vector is rescaled to the given size,
    keeping its direction. Any other name is a Scenario field and is set directly.
    """
    if quantity not in _VECTORS:
        return replace(s, **{quantity: value})
    names = _VECTORS[quantity]
    vector = np.array([getattr(s, n) for n in names])
    size = np.linalg.norm(vector)
    if size == 0:
        raise ValueError(f"scenario has no {quantity} direction to scale")
    return replace(s, **dict(zip(names, vector * (value / size))))


def matched_sweep(base: list[Scenario], quantity: str, values: list[float]) -> list[Scenario]:
    """Every base scenario at every value of one quantity, so that only that quantity differs.

    Returned in order: all base scenarios at values[0], then at values[1], and so on.
    """
    return [with_value(s, quantity, v) for v in values for s in base]


def run_scenario(
    model: mujoco.MjModel, s: Scenario, max_time: float = 180.0, config: ControllerConfig | None = None
) -> dict:
    """Run one scenario and return a flat row: the scenario's fields plus the result."""
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
    audit = Audit(model)
    r = run_trial(model, data, CaptureController(model, config, sensor=sensor), max_time=max_time, after_step=audit)
    return asdict(s) | audit.result(data) | {
        "outcome": r.outcome.value,
        "engaged": int(r.engaged),
        "seated": int(r.seated),
        "latched": int(r.latched),
        "retained": int(r.retained),
        "catchable_time": r.catchable_time,
        "close_speed": r.close_speed,
        "retention_tilt": r.retention_tilt,
        "duration": r.duration,
        "t_trigger": "" if r.t_trigger is None else r.t_trigger,
        "final_lateral": float(np.linalg.norm(r.offset[:2])),
        "final_depth": float(-r.offset[2]),
        "final_axis_error": r.axis_error,
        "final_rel_speed": r.rel_speed,
        "conditioning": r.conditioning,
    }


_model: mujoco.MjModel | None = None
_config: ControllerConfig | None = None


def _init_worker(build: dict, config: dict) -> None:
    global _model, _config
    # appearance is irrelevant here, and the model loads faster without meshes
    _model = scene.build_model(meshes=False, **build)
    _config = ControllerConfig(**config)


def _work(s: Scenario) -> dict:
    return run_scenario(_model, s, config=_config)


def run_batch(
    scenarios: list[Scenario],
    workers: int | None = None,
    build: dict | None = None,
    config: dict | None = None,
) -> list[dict]:
    """Run scenarios across processes. Results come back in the order given.

    build:  keyword arguments for scene.build_model, such as friction or snare_force.
    config: fields of ControllerConfig to change, such as max_joint_rate.
    """
    build, config = build or {}, config or {}
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    if workers == 1:
        _init_worker(build, config)
        return [_work(s) for s in scenarios]
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker, initargs=(build, config)) as pool:
        return pool.map(_work, scenarios, chunksize=1)


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarise(rows: list[dict]) -> str:
    counts = Counter(r["outcome"] for r in rows)
    lines = [f"{len(rows)} attempts"]
    for outcome in Outcome:
        n = counts.get(outcome.value, 0)
        lines.append(f"  {outcome.value:18s} {n:5d}  {100 * n / len(rows):5.1f}%")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a batch of random capture attempts.")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None, help="CSV file to write")
    for f in fields(Ranges):
        parser.add_argument(f"--{f.name.replace('_', '-')}", type=float, default=f.default, help="limit, SI units")
    args = parser.parse_args()

    ranges = Ranges(**{f.name: getattr(args, f.name) for f in fields(Ranges)})
    start = time.perf_counter()
    rows = run_batch(sample(args.n, ranges, args.seed), args.workers)
    print(summarise(rows))
    print(f"  {time.perf_counter() - start:.0f} s")
    if args.out:
        write_csv(rows, args.out)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
