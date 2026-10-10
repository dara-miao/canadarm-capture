# canadarm-capture

MuJoCo study of a station arm capturing a free-floating vehicle. Portfolio project; the build process is documented as carefully as the code.

## Documentation routine

Do this as part of every piece of work, not at the end:

- `docs/PLAN.md` is the living plan. When a milestone finishes or a decision changes, update the milestone table, the decision table, and the assumptions list.
- `docs/DEVLOG.md` is the build log. Add a dated entry per milestone or significant change: what was built, design choices, check results with numbers, what went wrong, what is not done.
- `docs/media/plan.svg` is the visual plan. Edit statuses in `scripts/plan_diagram.py` and rerun it. The user likes plans shown as a visual pipeline.
- Record failures and wrong turns honestly; they are part of the presentation.
- Label every approximate dimension, mass, or gain as approximate. Do not present the simulation as validated.

## Commands

- Tests: `.venv/bin/python -m pytest`
- Renders: `.venv/bin/python scripts/render_scene.py`
- Plan diagram: `.venv/bin/python scripts/plan_diagram.py`
- Fetch 3D models (git-ignored, needed for mesh renders): `.venv/bin/python scripts/fetch_assets.py`
- Interactive viewer: `.venv/bin/mjpython scripts/view.py`

## Constraints

- Must run on an Apple Silicon Mac, CPU only. No NVIDIA-only dependencies.
- MuJoCo first; Newton is a later second-engine comparison.

## Git

- One commit per milestone, authored by the user, pushed to `origin` (github.com/dara-miao/canadarm-capture).
- No `Co-Authored-By` line on commits. The README's "How this was built" section credits Claude Code instead.
- Update `docs/PLAN.md`, `docs/DEVLOG.md`, and the plan diagram in the same commit as the milestone they describe.
