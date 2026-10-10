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

## Where things stand (updated 2026-10-10)

Read `docs/PLAN.md` (questions, milestones, decisions), `docs/RESEARCH.md` (sources and numbers), and the last few entries of `docs/DEVLOG.md` before doing anything.

- Milestones 1 to 4 and R1 to R4 are done. The model has the Canadarm2 pull-in force, a latch stage, a retention check, and six outcome labels.
- Two questions lead the project, both written at the top of the plan:
  1. Which of the model's assumptions decide where the simulated capture fails? (`experiments/pilot_sensitivity.py`)
  2. Why do snared pins get lost? (`experiments/pilot_lost.py`)
- Both pilots are finished and written up in the build log entry "Pilot results". Summary tables are in `docs/data/`. Before rerunning a pilot because a table is missing, check it is not still running (`pgrep -fl experiments/pilot_`).
- Pilot findings in one line each: going limp when the snare closes doubles the drift speed at which capture fails (6 to 12 cm/s); friction, snare drive force, arm speed, and observation delay each move it by 1 cm/s or less; lost pins escape by pushing the snare bars past their soft open stop and apart from each other, which is an artefact of the rigid-bar snare. `experiments/replay_lost.py` shows this for single attempts.
- Open, for the user to decide: whether "limp at close" becomes the default, whether to harden the snare's stops and coupling, and what the full experiments A and B should be. Do not change the model or run the experiments unasked.
