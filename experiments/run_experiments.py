"""The three experiments: artefact checks (A), representation (B), physical unknowns (C).

    python experiments/run_experiments.py            # run whatever has not been run, then summarise
    python experiments/run_experiments.py B          # only experiment B's conditions
    python experiments/run_experiments.py summary    # only rebuild the summary tables

Every condition changes one thing from the baseline and runs the same scenarios, so
attempts can be compared in pairs. Per-attempt results go to results/experiments/ (not
kept in git); summary tables go to docs/data/. A condition whose results file exists is
not rerun, so the script can be stopped and restarted.

See docs/PLAN.md, "Proposed experiments", for what each condition is for.
"""

import csv
import math
import re
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from capture import batch  # noqa: E402
from capture.audit import FLAGS  # noqa: E402
from capture.trial import Outcome  # noqa: E402
from pilot_lost import HARSH  # noqa: E402

RAW = ROOT / "results" / "experiments"
DATA = ROOT / "docs" / "data"

# Shared scenarios for B and C: a matched drift sweep, with enough tumble that the
# fixture plate tilts onto the rim. Offsets, tilt, and roll at the tested worst case.
DRIFTS = [0.04, 0.08, 0.12, 0.16]  # [m/s]
PER_DRIFT, SEEDS = 30, (0, 1)
SWEEP = batch.Ranges(tumble=np.radians(2.0))
NUDGE = 1e-6  # [m]; a change with no physical meaning, to see how many outcomes flip anyway

# experiment, name, build options, controller options, scenario fields to override
CONDITIONS = [
    ("B", "baseline", {}, {}, {}),
    ("B", "noise floor: start nudged 0.001 mm", {}, {}, {"nudge": NUDGE}),
    ("B", "rim: box tops", {"rim": "boxes"}, {}, {}),
    ("B", "rim: 16 spheres", {"rim_spheres": 16}, {}, {}),
    ("B", "rim: 64 spheres", {"rim_spheres": 64}, {}, {}),
    ("B", "wall: 8 boxes", {"wall_segments": 8}, {}, {}),
    ("B", "wall: 32 boxes", {"wall_segments": 32}, {}, {}),
    ("B", "time step 1 ms", {"timestep": 0.001}, {}, {}),
    ("B", "time step 0.5 ms", {"timestep": 0.0005}, {}, {}),
    ("B", "contact twice as stiff", {"contact_time": 0.01}, {}, {}),
    ("C", "friction 0.1", {"friction": 0.1}, {}, {}),
    ("C", "friction 0.8", {"friction": 0.8}, {}, {}),
    ("C", "friction at the pin 0.1", {"friction_pin": 0.1}, {}, {}),
    ("C", "friction at the pin 0.8", {"friction_pin": 0.8}, {}, {}),
    ("C", "friction at the rim 0.1", {"friction_rim": 0.1}, {}, {}),
    ("C", "friction at the rim 0.8", {"friction_rim": 0.8}, {}, {}),
    ("C", "joint rate cap 0.015 rad/s", {}, {"max_joint_rate": 0.015}, {}),
    ("C", "joint rate cap 0.06 rad/s", {}, {"max_joint_rate": 0.06}, {}),
    ("C", "pull-in force 3,560 N", {"pull_in_force": 3560.0}, {}, {}),
    ("C", "pull-in force 6,100 N", {"pull_in_force": 6100.0}, {}, {}),
    ("C", "joint back-drive 100 N m", {"backdrive": 100.0}, {}, {}),
    ("C", "joint back-drive 400 N m", {"backdrive": 400.0}, {}, {}),
    ("C", "vehicle mass 5,000 kg", {"vehicle_mass": 5000.0}, {}, {}),
    ("C", "vehicle mass 8,050 kg", {"vehicle_mass": 8050.0}, {}, {}),
    ("C", "observation delay 0.5 s", {}, {}, {"sensor_delay": 0.5}),
    ("C", "observation delay 1.0 s", {}, {}, {"sensor_delay": 1.0}),
    ("C", "snare drive 750 N", {"snare_force": 750.0}, {}, {}),
    ("C", "snare drive 3,000 N", {"snare_force": 3000.0}, {}, {}),
    # Experiment A's test: the harsh pilot batch, where the box-top rim is known to fail.
    ("A", "harsh, box-top rim", {"rim": "boxes"}, {}, {}),
    ("A", "harsh, box-top rim, limp arm", {"rim": "boxes"}, {"limp_from_snare_close": True}, {}),
    ("A", "harsh, sphere rim", {}, {}, {}),
    ("A", "harsh, sphere rim, limp arm", {}, {"limp_from_snare_close": True}, {}),
]


def scenarios(experiment: str, override: dict) -> list[batch.Scenario]:
    if experiment == "A":
        out = batch.sample(60, HARSH, seed=0)
    else:
        out = [s for seed in SEEDS for s in batch.matched_sweep(batch.sample(PER_DRIFT, SWEEP, seed), "drift", DRIFTS)]
    for field, value in override.items():
        if field == "nudge":
            out = [replace(s, lateral_x=s.lateral_x + value) for s in out]
        else:
            out = [batch.with_value(s, field, value) for s in out]
    return out


def path_for(experiment: str, name: str) -> Path:
    return RAW / f"{experiment}_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}.csv"


def run(only: str | None) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for experiment, name, build, config, override in CONDITIONS:
        path = path_for(experiment, name)
        if (only and experiment != only) or path.exists():
            continue
        start = time.perf_counter()
        rows = batch.run_batch(scenarios(experiment, override), build=build, config=config)
        batch.write_csv(rows, path)
        counts = Counter(r["outcome"] for r in rows)
        print(f"{experiment} | {name}: {dict(counts)}  {time.perf_counter() - start:.0f} s", flush=True)


def load(experiment: str, name: str) -> list[dict] | None:
    path = path_for(experiment, name)
    if not path.exists():
        return None
    with path.open() as f:
        return list(csv.DictReader(f))


def interval(k: int, n: int) -> tuple[float, float]:
    """A 95% range for a rate measured as k out of n (the Wilson score interval)."""
    z = 1.96
    centre = (k + z * z / 2) / (n + z * z)
    half = z * math.sqrt(k * (n - k) / n + z * z / 4) / (n + z * z)
    return max(0.0, centre - half), min(1.0, centre + half)


def summarise() -> None:
    base = load("B", "baseline")
    out = []
    for experiment, name, *_ in CONDITIONS:
        rows = load(experiment, name)
        if rows is None or experiment == "A" or base is None:
            continue
        n = len(rows)
        captured = [r["outcome"] == "captured" for r in rows]
        k = sum(captured)
        lo, hi = interval(k, n)
        counts = Counter(r["outcome"] for r in rows)
        was = [r["outcome"] == "captured" for r in base]
        per_drift = {}
        for i, v in enumerate(DRIFTS):
            index = [j for j in range(n) if (j % (len(DRIFTS) * PER_DRIFT)) // PER_DRIFT == i]
            per_drift[f"captured_at_{v:.2f}"] = sum(captured[j] for j in index)
        out.append({
            "experiment": experiment, "condition": name, "attempts": n, "captured": k,
            "rate": round(k / n, 3), "rate_low": round(lo, 3), "rate_high": round(hi, 3),
            **per_drift,
            **{o.value: counts.get(o.value, 0) for o in Outcome if o is not Outcome.CAPTURED},
            # paired with the baseline, attempt by attempt
            "lost_a_capture": sum(w and not c for w, c in zip(was, captured)),
            "gained_a_capture": sum(c and not w for w, c in zip(was, captured)),
            "outcome_changed": sum(r["outcome"] != b["outcome"] for r, b in zip(rows, base)),
            "flagged": sum(bool(r["audit_flags"]) for r in rows),
        })  # fmt: skip
    if out:
        with (DATA / "experiments_b_c.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(out[0]))
            writer.writeheader()
            writer.writerows(out)
        print("wrote docs/data/experiments_b_c.csv")

    checks = []
    for experiment, name, *_ in CONDITIONS:
        rows = load(experiment, name)
        if rows is None or experiment != "A":
            continue
        flagged = [bool(r["audit_flags"]) for r in rows]
        lost = [r["outcome"] == "lost" for r in rows]
        checks.append({
            "condition": name, "attempts": len(rows),
            **{o.value: sum(r["outcome"] == o.value for r in rows) for o in Outcome},
            "flagged": sum(flagged),
            "lost_and_flagged": sum(a and b for a, b in zip(lost, flagged)),
            "not_lost_and_flagged": sum(b and not a for a, b in zip(lost, flagged)),
            **{f"flag_{name_}": sum(name_ in r["audit_flags"].split() for r in rows) for name_ in FLAGS},
        })  # fmt: skip
    if checks:
        with (DATA / "experiment_a_checks.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(checks[0]))
            writer.writeheader()
            writer.writerows(checks)
        print("wrote docs/data/experiment_a_checks.csv")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg != "summary":
        run(arg)
    summarise()
