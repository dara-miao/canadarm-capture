"""Pilot: why do snared pins get lost?

Reruns the harsh batch (drift to 0.122 m/s, tumble to 2 deg/s, degraded sensing) with
one thing changed at a time. Every variant runs the same 60 scenarios.

    python experiments/pilot_lost.py

Writes docs/data/pilot_lost.csv. A pilot: 60 attempts per variant, one seed.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import batch  # noqa: E402
from capture.trial import Outcome  # noqa: E402

HARSH = batch.Ranges(
    drift=0.122, tumble=np.radians(2.0),
    sensor_delay=0.5, sensor_rate=10.0, sensor_pos_noise=0.01, sensor_angle_noise=np.radians(1.0),
)  # fmt: skip

# name: (build options, controller options, scenario fields to override)
VARIANTS = {
    "baseline": ({}, {}, {}),
    "arm limp as soon as snare closes": ({}, {"limp_from_snare_close": True}, {}),
    "contact friction 0.6": ({"friction": 0.6}, {}, {}),
    "contact friction 0.1": ({"friction": 0.1}, {}, {}),
    "snare drive 3,000 N": ({"snare_force": 3000.0}, {}, {}),
    "snare drive 750 N": ({"snare_force": 750.0}, {}, {}),
    "perfect sensing": ({}, {}, {"sensor_delay": 0.0, "sensor_rate": 0.0, "sensor_pos_noise": 0.0, "sensor_angle_noise": 0.0}),
    "limp at close + perfect sensing": (
        {}, {"limp_from_snare_close": True},
        {"sensor_delay": 0.0, "sensor_rate": 0.0, "sensor_pos_noise": 0.0, "sensor_angle_noise": 0.0},
    ),
}  # fmt: skip


def main() -> None:
    base = batch.sample(60, HARSH, seed=0)
    out = []
    for name, (build, config, override) in VARIANTS.items():
        scenarios = base
        for field, value in override.items():
            scenarios = [batch.with_value(s, field, value) for s in scenarios]
        rows = batch.run_batch(scenarios, build=build, config=config)
        counts = Counter(r["outcome"] for r in rows)
        engaged = [r for r in rows if r["engaged"]]
        speed = float(np.median([r["close_speed"] for r in engaged])) if engaged else float("nan")
        record = {"variant": name, **{o.value: counts.get(o.value, 0) for o in Outcome},
                  "engaged": len(engaged), "median_close_speed_cm_s": round(100 * speed, 2)}  # fmt: skip
        out.append(record)
        print(record, flush=True)
    path = ROOT / "docs" / "data" / "pilot_lost.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
