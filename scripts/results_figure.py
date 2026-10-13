"""Draw the write-up's two figures, each in a light and a dark version.

    python scripts/results_figure.py

docs/media/results.svg     what moved the result (from docs/data/experiments.csv)
docs/media/rim.svg         one attempt on the old rim and the fixed one (from
                           docs/data/rim_force_trace.csv; experiments/trace_rim_force.py)

The dark versions end in -dark.svg. Colours are the first two slots of a palette checked
for colour-blind separation and contrast on both backgrounds.
"""

import csv
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
OUT = ROOT / "docs" / "media"
FONT = "-apple-system, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"

THEMES = {
    "": dict(surface="#fcfcfb", ink="#0b0b0b", muted="#52514e", grid="#e4e3df", neutral="#8a8983", a="#2a78d6", b="#eb6834"),
    "-dark": dict(surface="#1a1a19", ink="#ffffff", muted="#c3c2b7", grid="#34332f", neutral="#8a8983", a="#3987e5", b="#d95926"),
}  # fmt: skip

# label, the conditions it covers, series ("a" representation, "b" physical), note
ROWS = [
    ("How contact is represented", None, None, None),
    ("Rim: 16 or 64 spheres instead of 32", ["rim: 16 spheres", "rim: 64 spheres"], "a", None),
    ("Time step four times finer", ["time step 0.5 ms"], "a", None),
    ("Cavity wall: 8 or 32 boxes instead of 16", ["wall: 8 boxes", "wall: 32 boxes"], "a", None),
    ("Contact twice as stiff", ["contact twice as stiff"], "a", None),
    ("Rim: the tops of the wall boxes", ["rim: box tops"], "a", "broke the solver; caught only by the checks"),
    ("Physical numbers not known exactly", None, None, None),
    ("Snare drive force (control)", ["snare drive 750 N", "snare drive 3,000 N"], "b", None),
    ("Friction where the snare holds the pin", ["friction at the pin 0.1", "friction at the pin 0.8"], "b", None),
    ("Joint back-drive friction", ["joint back-drive 100 N m", "joint back-drive 400 N m"], "b", None),
    ("Observation delay", ["observation delay 0.5 s", "observation delay 1.0 s"], "b", None),
    ("Friction where the fixture seats on the rim", ["friction at the rim 0.1", "friction at the rim 0.8"], "b", None),
    ("How fast the arm's joints may turn", ["joint rate cap 0.015 rad/s", "joint rate cap 0.06 rad/s"], "b", None),
]  # fmt: skip


def text(x, y, s, fill, size=14, weight=400, anchor="start", extra="") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"{extra}>{escape(s)}</text>'


def frame(width: int, height: int, c: dict, title: str, subtitle: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="{FONT}" role="img" aria-label="{escape(description)}">',
        f"<title>{escape(title)}</title><desc>{escape(description)}</desc>",
        f'<rect width="{width}" height="{height}" rx="14" fill="{c["surface"]}"/>',
        text(32, 44, title, c["ink"], 20, 700),
        text(32, 70, subtitle, c["muted"], 14),
    ]


def results(c: dict) -> str:
    with (DATA / "experiments.csv").open() as f:
        changed = {r["condition"]: int(r["outcome_changed"]) for r in csv.DictReader(f)}
    noise = changed["noise floor: start nudged 0.001 mm"]

    width, left, right, top = 1000, 372, 60, 150
    row_h, bar_h, head_h = 32, 16, 42
    plot_w = width - left - right
    scale = plot_w / 200.0  # the axis runs to 200 attempts
    bottom = top + sum(head_h if r[1] is None else row_h for r in ROWS) + 6
    height = bottom + 118
    parts = frame(
        width, height, c,
        "Physical unknowns moved the result far more than how contact was represented",
        "Attempts, out of 240, that ended differently from the baseline when one thing was changed",
        "Bar chart. Sound changes to how contact is represented changed at most 7 of 240 outcomes, near a noise floor of 3. "
        "The old box-top rim changed 79. Physical unknowns changed up to 180.",
    )  # fmt: skip
    # legend
    lx, ly = 32, 104
    for key, label in (("a", "How contact is represented"), ("b", "Physical numbers not known exactly")):
        parts.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="2" fill="{c[key]}"/>')
        parts.append(text(lx + 19, ly, label, c["muted"], 13))
        lx += 19 + 7.1 * len(label) + 26
    parts.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" fill="{c["neutral"]}" opacity="0.4"/>')
    parts.append(text(lx + 19, ly, f"Noise floor: {noise} outcomes change when nothing meaningful does", c["muted"], 13))

    for tick in (0, 50, 100, 150, 200):
        x = left + tick * scale
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{c["grid"]}" stroke-width="1"/>')
        parts.append(text(x, bottom + 20, str(tick), c["muted"], 13, anchor="middle", extra=' style="font-variant-numeric: tabular-nums"'))
    parts.append(f'<rect x="{left}" y="{top}" width="{noise * scale:.1f}" height="{bottom - top}" fill="{c["neutral"]}" opacity="0.4"/>')
    parts.append(text(left + plot_w / 2, bottom + 44, "Attempts whose outcome changed, of 240", c["muted"], 13, anchor="middle"))

    y = top
    for label, conditions, series, note in ROWS:
        if conditions is None:
            parts.append(text(32, y + 28, label, c["ink"], 14, 700))
            y += head_h
            continue
        value = max(changed[k] for k in conditions)
        w = max(value * scale, 3)
        mid = y + row_h / 2
        parts.append(text(left - 14, mid + 5, label, c["ink"], 14, anchor="end"))
        parts.append(
            f'<path d="M{left},{mid - bar_h / 2} h{max(w - 4, 0):.1f} a4,4 0 0 1 4,4 v{bar_h - 8} a4,4 0 0 1 -4,4 h-{max(w - 4, 0):.1f} z" fill="{c[series]}">'
            f"<title>{escape(label)}: {value} of 240</title></path>"
        )
        parts.append(text(left + w + 8, mid + 5, str(value), c["ink"], 14, 600))
        if note:
            parts.append(text(left + w + 42, mid + 5, note, c["muted"], 13))
        y += row_h
    parts.append(text(32, height - 40, "Each bar is the larger effect of the settings tried for that item. 240 simulated attempts per condition:", c["muted"], 12))
    parts.append(text(32, height - 22, "4 drift speeds × 30 scenarios × 2 random seeds, compared attempt by attempt with the baseline. Simulation only.", c["muted"], 12))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def rim(c: dict) -> str:
    with (DATA / "rim_force_trace.csv").open() as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    t = [r["seconds_after_firing"] for r in rows]
    series = {
        "b": [100 * r["vehicle_speed_box_top_rim_m_s"] for r in rows],
        "a": [100 * r["vehicle_speed_sphere_rim_m_s"] for r in rows],
    }
    peak = {"b": max(r["force_box_top_rim_N"] for r in rows), "a": max(r["force_sphere_rim_N"] for r in rows)}
    contact = next(r["seconds_after_firing"] for r in rows if r["force_box_top_rim_N"] > 0)

    width, height, left, right, top, bottom = 1000, 546, 78, 250, 150, 420
    x0, x1, y_max = 6.0, 10.0, 30.0
    sx = lambda v: left + (v - x0) / (x1 - x0) * (width - left - right)  # noqa: E731
    sy = lambda v: bottom - v / y_max * (bottom - top)  # noqa: E731
    parts = frame(
        width, height, c,
        "One contact, modelled two ways: on the old rim it threw the ship off",
        "Speed of the 7-tonne vehicle relative to the station in one simulated attempt, after the snare has closed on its pin",
        "Line chart of vehicle speed against time for one attempt. With the rim as box tops the speed jumps from 2 to over 20 cm/s "
        "when the fixture plate meets the rim. With the rim as a ring of spheres it stays near 2 cm/s.",
    )  # fmt: skip
    lx, ly = 32, 104
    for key, label in (("b", "Rim as the tops of the wall boxes"), ("a", "Rim as a ring of spheres")):
        parts.append(f'<line x1="{lx}" y1="{ly - 5}" x2="{lx + 18}" y2="{ly - 5}" stroke="{c[key]}" stroke-width="2" stroke-linecap="round"/>')
        parts.append(text(lx + 25, ly, label, c["muted"], 13))
        lx += 25 + 7.1 * len(label) + 26

    for tick in (0, 10, 20, 30):
        parts.append(f'<line x1="{left}" y1="{sy(tick):.1f}" x2="{width - right}" y2="{sy(tick):.1f}" stroke="{c["grid"]}" stroke-width="1"/>')
        parts.append(text(left - 10, sy(tick) + 5, str(tick), c["muted"], 13, anchor="end", extra=' style="font-variant-numeric: tabular-nums"'))
    for tick in (6, 7, 8, 9, 10):
        parts.append(text(sx(tick), bottom + 22, str(tick), c["muted"], 13, anchor="middle", extra=' style="font-variant-numeric: tabular-nums"'))
    parts.append(text(left + (width - left - right) / 2, bottom + 48, "Seconds after the snare fires", c["muted"], 13, anchor="middle"))
    parts.append(text(32, top - 16, "Vehicle speed, cm/s", c["muted"], 13))

    # where the plate meets the rim
    parts.append(f'<line x1="{sx(contact):.1f}" y1="{top}" x2="{sx(contact):.1f}" y2="{bottom}" stroke="{c["muted"]}" stroke-width="1"/>')
    parts.append(text(sx(contact) - 8, top + 14, "the tilted fixture plate", c["muted"], 13, anchor="end"))
    parts.append(text(sx(contact) - 8, top + 31, "meets the rim", c["muted"], 13, anchor="end"))

    for key in ("a", "b"):
        pts = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in list(zip(t, series[key]))[::5])
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{c[key]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        end_y = sy(series[key][-1])
        parts.append(f'<circle cx="{sx(t[-1]):.1f}" cy="{end_y:.1f}" r="5" fill="{c[key]}" stroke="{c["surface"]}" stroke-width="2"/>')
        outcome, force = ("Lost", f"{peak[key] / 1e6:.0f} million N") if key == "b" else ("Captured", f"{peak[key] / 1e3:.1f} thousand N")
        lx = sx(t[-1]) + 14
        parts.append(text(lx, end_y - 3, f"{outcome}: {series[key][-1]:.0f} cm/s", c["ink"], 14, 600))
        parts.append(text(lx, end_y + 15, f"peak force at the rim {force}", c["muted"], 12))
    parts.append(text(32, height - 40, "The two runs are identical except for the collision shape of the rim. A contact cannot add energy to the vehicle, so the jump", c["muted"], 12))
    parts.append(text(32, height - 22, "is the solver failing, not physics. Everything the machine can apply to the vehicle is about 69 thousand N. Simulation only.", c["muted"], 12))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    for suffix, colours in THEMES.items():
        for name, draw in (("results", results), ("rim", rim)):
            path = OUT / f"{name}{suffix}.svg"
            path.write_text(draw(colours))
            print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
