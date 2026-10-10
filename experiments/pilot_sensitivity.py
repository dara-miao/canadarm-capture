"""Pilot: which assumptions decide where the simulated capture fails?

Sweeps drift speed with everything else matched, then repeats the sweep with one
assumption changed at a time. The "failure point" is the drift speed at which the
capture rate crosses 50%, by linear interpolation between the speeds tested.

    python experiments/pilot_sensitivity.py

Writes docs/data/pilot_sensitivity.csv. A pilot: 12 scenarios per speed, one seed.
"""

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import batch  # noqa: E402

DRIFTS = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15]  # [m/s]
BASE = batch.Ranges()  # offsets, tilts, roll, and tumble at their defaults; perfect sensing

# name: (build options, controller options, scenario fields to override)
VARIANTS = {
    "baseline": ({}, {}, {}),
    "contact friction 0.1": ({"friction": 0.1}, {}, {}),
    "contact friction 0.6": ({"friction": 0.6}, {}, {}),
    "joint rate cap halved (0.015 rad/s)": ({}, {"max_joint_rate": 0.015}, {}),
    "joint rate cap doubled (0.06 rad/s)": ({}, {"max_joint_rate": 0.06}, {}),
    "snare drive 750 N": ({"snare_force": 750.0}, {}, {}),
    "snare drive 3,000 N": ({"snare_force": 3000.0}, {}, {}),
    "observation delay 0.5 s": ({}, {}, {"sensor_delay": 0.5}),
    "observation delay 1.0 s": ({}, {}, {"sensor_delay": 1.0}),
    "estimator gain 0.05": ({}, {"measurement_gain": 0.05}, {}),
    "estimator gain 1.0": ({}, {"measurement_gain": 1.0}, {}),
    "arm limp as soon as snare closes": ({}, {"limp_from_snare_close": True}, {}),
}


def failure_point(rates: list[float]) -> float | None:
    """Drift speed where the capture rate first falls through 0.5, or None if it never does."""
    for (v0, r0), (v1, r1) in zip(zip(DRIFTS, rates), zip(DRIFTS[1:], rates[1:])):
        if r0 >= 0.5 > r1:
            return v0 + (r0 - 0.5) / (r0 - r1) * (v1 - v0)
    return None


def main() -> None:
    base = batch.sample(12, BASE, seed=1)
    out = []
    for name, (build, config, override) in VARIANTS.items():
        scenarios = batch.matched_sweep(base, "drift", DRIFTS)
        for field, value in override.items():
            scenarios = [batch.with_value(s, field, value) for s in scenarios]
        rows = batch.run_batch(scenarios, build=build, config=config)
        rates = []
        for i, _ in enumerate(DRIFTS):
            chunk = rows[i * len(base) : (i + 1) * len(base)]
            rates.append(sum(r["outcome"] == "captured" for r in chunk) / len(chunk))
        point = failure_point(rates)
        record = {"variant": name, **{f"captured_at_{v:.2f}": round(r, 2) for v, r in zip(DRIFTS, rates)},
                  "failure_point_m_s": "" if point is None else round(point, 3)}  # fmt: skip
        out.append(record)
        print(record, flush=True)
    path = ROOT / "docs" / "data" / "pilot_sensitivity.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
