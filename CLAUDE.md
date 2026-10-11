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
- Three pilots are finished and written up in the build log (entries of 2026-10-10 and 2026-10-11). Tables are in `docs/data/`. Before rerunning a pilot because a table is missing, check it is not still running (`pgrep -fl experiments/pilot_`).
- Main finding so far (`experiments/pilot_load.py`): every lost capture in the harsh batch is a numerical contact failure. The vehicle keeps tumbling after the snare closes, the fixture plate tilts 5 to 12° into the end effector's rim, and the solver returns forces up to 2.3 MN that add energy and throw the vehicle off. Earlier explanations (relative speed, snare drive, soft stops, momentum) are superseded. "Lost" counts in all batches so far count this artefact.
- Likely cause, not established: the cavity wall's 16 overlapping boxes (`scene._add_cavity_wall`) give redundant contacts with the plate.
- Sensitivity pilot: going limp when the snare closes moved the failure point from 6 to 12 cm/s of drift; other changes moved it by 1 cm/s or less. It saved no failure types, so how much of that is the same artefact is unknown.
- Open, for the user to decide: how to fix the plate-on-rim contact, then whether to rerun the pilots. Experiments A and B are on hold until then. Do not change the model or run experiments unasked.
- Two Claude Code sessions once edited this repository at the same time and their work was mixed in one commit. Check `git status` and `git log` before editing.
