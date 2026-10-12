"""Draw the project plan as docs/media/plan.svg.

Edit STAGES / EXPERIMENTS below when the plan or a status changes, then rerun.
Status is one of: "done", "next", "planned".
"""

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "media" / "plan.svg"

# (label, title, line 1, line 2, status)
STAGES = [
    ("1 · ZERO-G WORLD", "Build the scene", "7-joint arm · drifting vehicle", "Grapple pin · hollow end effector", "done"),
    ("2 · GRAPPLE MECHANISM", "Model the snare", "Closing mechanism on the pin", "Contact friction + compliance", "done"),
    ("3 · CLOSED LOOP", "Approach and capture", "Track the pin · trigger the snare", "Arm tracks a drifting pin", "done"),
    ("4 · REPEATABLE TRIALS", "Measure outcomes", "Success criteria · failure types", "Outcome labels · batches · sensing", "done"),
]
EXPERIMENTS = [
    ("5 · EXPERIMENT A", "Artefact checks", "Force, energy, overlap on every attempt", "Caught 50 of 50, and found more", "done"),
    ("6 · EXPERIMENT B", "Same surface, new shape", "Rim · wall · time step · stiffness", "Result survives; old rim does not", "done"),
    ("7 · EXPERIMENT C", "Physical unknowns", "Each guessed number across its range", "Rate cap, rim friction, delay lead", "done"),
]

# One line on what is happening right now, shown under the title.
NOW = "Experiments done.  Next: explain the attempts the checks still flag, then the write-up."

W, H = 1600, 860
BG, CARD, EDGE = "#0f1b2d", "#1b2a40", "#2b3d57"
ACCENT, TEXT, MUTED, FLOW = "#b9e36b", "#ffffff", "#a9b7c9", "#8fd3e8"
STATUS = {"done": ("DONE", "#7fd36b"), "next": ("NEXT", "#f2b84b"), "planned": ("PLANNED", "#6f8098")}

CARD_W, CARD_H, GAP = 340, 190, 40
X0 = (W - 4 * CARD_W - 3 * GAP) // 2
Y1, Y2 = 200, 520
FONT = "-apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif"


def col_x(i: int) -> int:
    return X0 + i * (CARD_W + GAP)


def card(x: int, y: int, label: str, title: str, l1: str, l2: str, status: str) -> str:
    name, color = STATUS[status]
    chip_w = 20 + 9 * len(name)
    return f"""
  <rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="14" fill="{CARD}" stroke="{color if status != 'planned' else EDGE}" stroke-width="{2 if status != 'planned' else 1}"/>
  <text x="{x + 22}" y="{y + 40}" fill="{ACCENT}" font-size="15" font-weight="700" letter-spacing="0.5">{escape(label)}</text>
  <text x="{x + 22}" y="{y + 82}" fill="{TEXT}" font-size="27" font-weight="700">{escape(title)}</text>
  <text x="{x + 22}" y="{y + 118}" fill="{MUTED}" font-size="17">{escape(l1)}</text>
  <text x="{x + 22}" y="{y + 144}" fill="{MUTED}" font-size="17">{escape(l2)}</text>
  <rect x="{x + CARD_W - chip_w - 16}" y="{y + CARD_H - 38}" width="{chip_w}" height="24" rx="12" fill="{color}"/>
  <text x="{x + CARD_W - chip_w / 2 - 16}" y="{y + CARD_H - 21}" fill="{BG}" font-size="12" font-weight="700" text-anchor="middle" letter-spacing="0.5">{name}</text>"""


def main() -> None:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f"""  <defs>
    <marker id="a" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker>
    <marker id="b" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{FLOW}"/></marker>
  </defs>
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <text x="{X0}" y="70" fill="{ACCENT}" font-size="18" font-weight="700" letter-spacing="1">THE PLAN</text>
  <text x="{X0}" y="130" fill="{TEXT}" font-size="46" font-weight="700">One capture model. Three robustness experiments.</text>
  <text x="{X0}" y="168" fill="{STATUS['next'][1]}" font-size="17" font-weight="600">{escape(NOW)}</text>""",
    ]

    for i, s in enumerate(STAGES):
        parts.append(card(col_x(i), Y1, *s))
        if i < len(STAGES) - 1:
            x = col_x(i) + CARD_W
            parts.append(f'  <line x1="{x + 6}" y1="{Y1 + CARD_H / 2}" x2="{x + GAP - 6}" y2="{Y1 + CARD_H / 2}" stroke="{ACCENT}" stroke-width="3" marker-end="url(#a)"/>')

    # Trial harness feeds every experiment through one bus line.
    bus_y = (Y1 + CARD_H + Y2) // 2
    src_x = col_x(3) + CARD_W // 2
    centers = [col_x(i + 1) + CARD_W // 2 for i in range(len(EXPERIMENTS))]
    parts.append(f'  <path d="M{src_x},{Y1 + CARD_H} V{bus_y} H{centers[0]}" fill="none" stroke="{FLOW}" stroke-width="3"/>')
    for cx in centers:
        parts.append(f'  <line x1="{cx}" y1="{bus_y}" x2="{cx}" y2="{Y2 - 6}" stroke="{FLOW}" stroke-width="3" marker-end="url(#b)"/>')
    for i, e in enumerate(EXPERIMENTS):
        parts.append(card(col_x(i + 1), Y2, *e))

    parts.append(f"""  <text x="{X0}" y="{Y2 + 70}" fill="{ACCENT}" font-size="20" font-weight="600">Same scene and trial</text>
  <text x="{X0}" y="{Y2 + 98}" fill="{ACCENT}" font-size="20" font-weight="600">harness, reused</text>
  <text x="{X0}" y="{Y2 + 132}" fill="{MUTED}" font-size="17">Each experiment changes</text>
  <text x="{X0}" y="{Y2 + 156}" fill="{MUTED}" font-size="17">only what it is testing</text>
  <text x="{X0}" y="{H - 50}" fill="{TEXT}" font-size="21">Build the world  /  add the mechanism  /  close the loop  /  measure  /  experiment  /  write up</text>
</svg>""")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts) + "\n")
    print("wrote", OUT.relative_to(OUT.parent.parent.parent))


if __name__ == "__main__":
    main()
