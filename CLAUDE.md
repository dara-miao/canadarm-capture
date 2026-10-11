# canadarm-capture

MuJoCo study of a station arm capturing a free-floating vehicle. Portfolio project; the build process is documented as carefully as the code.

## Documentation routine

Do this as part of every piece of work, not at the end:

- `docs/PLAN.md` is the living plan. When a milestone finishes or a decision changes, update the milestone table, the decision table, and the assumptions list.
- `docs/RESEARCH.md` is the research notes: what is known about the real operation, with every claim labelled Read, Reported, Assumed, or Disputed. Add new findings there first, with the source and what kind of number it is (requirement, measured value, or a modelling paper's input). Keep short quotations with the author named; do not copy long passages. When the user brings research from another tool, record it as Reported until the source itself has been read.
- `docs/DEVLOG.md` is the build log. Add a dated entry per milestone or significant change: what was built, design choices, check results with numbers, what went wrong, what is not done.
- `docs/media/plan.svg` is the visual plan. Edit statuses in `scripts/plan_diagram.py` and rerun it. The user likes plans shown as a visual pipeline.
- Record failures and wrong turns honestly; they are part of the presentation.
- Label every approximate dimension, mass, or gain as approximate. Do not present the simulation as validated.

## Commands

- Tests: `.venv/bin/python -m pytest`
- Batch of attempts: `.venv/bin/python -m capture.batch --n 100 --seed 0 --out results/name.csv` (results/ is git-ignored)
- Renders: `.venv/bin/python scripts/render_scene.py`
- Plan diagram: `.venv/bin/python scripts/plan_diagram.py`
- Fetch 3D models (git-ignored, needed for mesh renders): `.venv/bin/python scripts/fetch_assets.py`
- Interactive viewer: `.venv/bin/mjpython scripts/view.py`

## Constraints

- Research first. The user wants to understand the real operation well before running experiments or writing about them. Do not start an experiment or change model parameters on new research without checking with the user.
- Must run on an Apple Silicon Mac, CPU only. No NVIDIA-only dependencies.
- MuJoCo first; Newton is a later second-engine comparison.
- The interactive viewer uses more than a full core. Close it before running batches, and keep batches modest when the user is on battery.

## Git

- One commit per milestone, authored by the user, pushed to `origin` (github.com/dara-miao/canadarm-capture).
- No `Co-Authored-By` line on commits. The README's "How this was built" section credits Claude Code instead.
- Update `docs/PLAN.md`, `docs/DEVLOG.md`, and the plan diagram in the same commit as the milestone they describe.

## Where things stand (updated 2026-10-11)

Read `docs/PLAN.md` (questions, milestones, decisions), `docs/RESEARCH.md` (sources and numbers), and the last few entries of `docs/DEVLOG.md` before doing anything.

- Milestones 1 to 4 and R1 to R4 are done. The model has the Canadarm2 pull-in force, a latch stage, a retention check, and six outcome labels.
- Two questions lead the project, both written at the top of the plan:
  1. Which of the model's assumptions decide where the simulated capture fails? (`experiments/pilot_sensitivity.py`)
  2. Why do snared pins get lost? (`experiments/pilot_lost.py`)
- Pilots so far are written up in the build log (entries of 2026-10-10 and 2026-10-11). Tables are in `docs/data/`; files ending `_box_rim` are from before the rim fix. Before rerunning a pilot because a table is missing, check it is not still running (`pgrep -fl experiments/pilot_`).
- Found 2026-10-11: every "lost" capture was a numerical contact failure where the tilted fixture plate met the tops of the overlapping wall boxes. Fixed the same day: the plate now seats on a ring of spheres (`scene._add_rim`; `rim="boxes"` rebuilds the old rim). In the harsh batch all 30 snared attempts are now captured, in every variant except friction 0.6 (10 captured, 20 caught but not rigid).
- All batch results from before the fix, including the sensitivity pilot's "limp at close doubles the failure point", describe the old rim. `docs/data/pilot_sensitivity.csv` does not exist yet: the sensitivity pilot still has to be rerun (about 20 minutes on all cores; it was held because the laptop was on low battery).
- Question 2 in the plan is answered and question 1 has lost its main pilot result. The questions need restating with the user before experiments A and B are designed. Do not run them unasked.
- When investigating a failure, log contact forces and kinetic energy before explaining it. Three explanations of lost pins were written before anyone did.
- Two Claude Code sessions once edited this repository at the same time and their work was mixed in one commit. Check `git status` and `git log` before editing.
