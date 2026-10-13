"""Draw the experiments' headline result as docs/media/results.svg.

    python scripts/results_figure.py

Reads docs/data/experiments_b_c.csv. For each thing changed, the bar is how many of the
240 attempts ended differently from the baseline, taking the larger of its settings.
"""

import csv
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "media" / "results.svg"

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
NOISE, SHAPE, PHYSICS = "#8a8983", "#2a78d6", "#eb6834"
FONT = "-apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif"

# label, the conditions it covers, colour, note
ROWS = [
    ("How contact is represented", None, None, None),
    ("Rim: 16 or 64 spheres instead of 32", ["rim: 16 spheres", "rim: 64 spheres"], SHAPE, None),
    ("Time step four times finer", ["time step 0.5 ms"], SHAPE, None),
    ("Cavity wall: 8 or 32 boxes instead of 16", ["wall: 8 boxes", "wall: 32 boxes"], SHAPE, None),
    ("Contact twice as stiff", ["contact twice as stiff"], SHAPE, None),
    ("Rim: the tops of the wall boxes", ["rim: box tops"], SHAPE, "broke the solver; caught only by the checks"),
    ("Physical numbers not known exactly", None, None, None),
    ("Snare drive force (control)", ["snare drive 750 N", "snare drive 3,000 N"], PHYSICS, None),
    ("Friction where the snare holds the pin", ["friction at the pin 0.1", "friction at the pin 0.8"], PHYSICS, None),
    ("Joint back-drive friction", ["joint back-drive 100 N m", "joint back-drive 400 N m"], PHYSICS, None),
    ("Observation delay", ["observation delay 0.5 s", "observation delay 1.0 s"], PHYSICS, None),
    ("Friction where the fixture seats on the rim", ["friction at the rim 0.1", "friction at the rim 0.8"], PHYSICS, None),
    ("How fast the arm's joints may turn", ["joint rate cap 0.015 rad/s", "joint rate cap 0.06 rad/s"], PHYSICS, None),
]  # fmt: skip


def main() -> None:
    with (ROOT / "docs" / "data" / "experiments_b_c.csv").open() as f:
        changed = {r["condition"]: int(r["outcome_changed"]) for r in csv.DictReader(f)}
    noise = changed["noise floor: start nudged 0.001 mm"]

    width, left, right, top = 1000, 372, 70, 118
    row_h, bar_h, head_h = 34, 16, 44
    plot_w = width - left - right
    scale = plot_w / 200.0  # the axis runs to 200 attempts
    height = top + sum(head_h if r[1] is None else row_h for r in ROWS) + 62
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" rx="14" fill="{SURFACE}"/>',
        f'<text x="32" y="46" fill="{INK}" font-size="22" font-weight="700">What moved the result</text>',
        f'<text x="32" y="74" fill="{MUTED}" font-size="15">Attempts, out of 240, that ended differently when one thing was changed.</text>',
    ]
    bottom = height - 62
    for tick in (0, 50, 100, 150, 200):
        x = left + tick * scale
        parts.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{bottom}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{x}" y="{bottom + 20}" fill="{MUTED}" font-size="13" text-anchor="middle">{tick}</text>')
    # the noise floor, as a band every bar can be read against
    parts.append(f'<rect x="{left}" y="{top - 6}" width="{noise * scale:.1f}" height="{bottom - top + 6}" fill="{NOISE}" opacity="0.28"/>')
    parts.append(f'<text x="{left + noise * scale + 8}" y="{top - 14}" fill="{MUTED}" font-size="13">noise floor: {noise} attempts change when nothing meaningful does</text>')

    y = top
    for label, conditions, colour, note in ROWS:
        if conditions is None:
            parts.append(f'<text x="32" y="{y + 28}" fill="{INK}" font-size="15" font-weight="700">{escape(label)}</text>')
            y += head_h
            continue
        value = max(changed[c] for c in conditions)
        w = max(value * scale, 2)
        mid = y + row_h / 2
        parts.append(f'<text x="{left - 14}" y="{mid + 5}" fill="{INK}" font-size="14" text-anchor="end">{escape(label)}</text>')
        parts.append(
            f'<path d="M{left},{mid - bar_h / 2} h{max(w - 4, 0):.1f} a4,4 0 0 1 4,4 v{bar_h - 8} a4,4 0 0 1 -4,4 h-{max(w - 4, 0):.1f} z" fill="{colour}">'
            f"<title>{escape(label)}: {value} of 240</title></path>"
        )
        parts.append(f'<text x="{left + w + 8}" y="{mid + 5}" fill="{INK}" font-size="14" font-weight="600">{value}</text>')
        if note:
            parts.append(f'<text x="{left + w + 40}" y="{mid + 5}" fill="{MUTED}" font-size="13">{escape(note)}</text>')
        y += row_h
    parts.append(f'<text x="{left + plot_w / 2}" y="{bottom + 44}" fill="{MUTED}" font-size="13" text-anchor="middle">attempts whose outcome changed</text>')
    parts.append("</svg>")
    OUT.write_text("\n".join(parts) + "\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
