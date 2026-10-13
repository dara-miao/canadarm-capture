# canadarm-capture

MuJoCo study of a station arm capturing a free-floating vehicle. Portfolio project; the build process is documented as carefully as the code.

The question (agreed 2026-10-11): when a contact-rich simulation gives a result, how do you tell whether it is physics or an artefact of how contact was modelled, and which modelling choices is the result most sensitive to? The capture is the case study. It solves no problem for the space industry.

## How to work with Dara

Dara wants to be the one who builds this and to understand the system design well enough to explain it. Explain before changing. Prefer walking Dara through a change, or having them make it and predict the result, over doing it silently. The plan lists five layers (world, contact, machine, brain, experiment); the agreed path is to go through them one at a time, starting with contact.

## Documentation routine

Do this as part of every piece of work, not at the end:

- `docs/PLAN.md` is the living plan. When a milestone finishes or a decision changes, update the milestone table, the decision table, and the assumptions list.
- `docs/RESEARCH.md` is the research notes: what is known about the real operation, with every claim labelled Read, Reported, Assumed, or Disputed. Add new findings there first, with the source and what kind of number it is (requirement, measured value, or a modelling paper's input). Keep short quotations with the author named; do not copy long passages. When the user brings research from another tool, record it as Reported until the source itself has been read.
- `docs/DEVLOG.md` is the build log. Add a dated entry per milestone or significant change: what was built, design choices, check results with numbers, what went wrong, what is not done.
- Log only what matters to the project's question: changes to the model or controller, experiments and their results, findings, decisions, and things that went wrong. Do not log cosmetic or housekeeping work (the sky, videos, viewer options, how the documents are written). Those go in the commit message and nowhere else.
- `docs/media/plan.svg` is the visual plan. Edit statuses in `scripts/plan_diagram.py` and rerun it. The user likes plans shown as a visual pipeline.
- Voice. The plan, research notes, and build log are Dara's documents. Write them as plain notes with no narrator, or in Dara's first person where it is a personal note (an aim, a decision, a question, something Dara did). Never write them from Claude's point of view, and never refer to Dara by name or as "the user". Do not put Dara's "I" on work Dara did not do: describe that neutrally ("eight attempts were replayed", "the sources were checked"). The README's "How this was built" section is where Claude Code is credited.
- Record failures and wrong turns honestly; they are part of the presentation.
- Label every approximate dimension, mass, or gain as approximate. Do not present the simulation as validated.

## Commands

- Tests: `.venv/bin/python -m pytest`
- Batch of attempts: `.venv/bin/python -m capture.batch --n 100 --seed 0 --out results/name.csv` (results/ is git-ignored)
- Renders: `.venv/bin/python scripts/render_scene.py`
- Preview video (needs ffmpeg): `.venv/bin/python scripts/render_preview.py`, then remake `docs/media/preview.gif` from it for the README
- Plan diagram: `.venv/bin/python scripts/plan_diagram.py`
- Fetch 3D models (git-ignored, needed for mesh renders): `.venv/bin/python scripts/fetch_assets.py`
- Starry background (git-ignored, appearance only): `.venv/bin/python scripts/make_sky.py`
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

## Where things stand (updated 2026-10-12)

Read `README.md` (the write-up), `docs/PLAN.md` (question, experiments, decisions, assumptions), and `docs/DEVLOG.md` before doing anything. All three were trimmed on 2026-10-12; longer versions are in the git history.

- The model is built and two experiments are run (`experiments/run_experiments.py`; tables in `docs/data/`): experiment 1 is collision geometry, experiment 2 is the physical unknowns. The checks in `capture/audit.py` are a guardrail, not an experiment. More than 10,000 attempts have been simulated in all. Of 240 attempts: noise floor 3 changed outcomes; sound representation changes at most 7; the old box-top rim 79; physical unknowns up to 180 (joint rate cap), 96 (friction at the rim), 68 (observation delay).
- Every "lost" capture before 2026-10-11 was a numerical contact failure at the rim. The plate now seats on a ring of spheres (`scene._add_rim`; `rim="boxes"` rebuilds the old rim). Data files ending `_box_rim` are from before the fix.
- `capture/audit.py` flags attempts that do not look like physics, in every batch. On the fixed model it still flags two things, both traced with `experiments/replay_flagged.py`: the end effector running into the hull during a failed approach (the arm's motors have no torque limit), and the pin's knob wedging between the rigid snare bars at low friction. Neither changes a capture count.
- The README is the write-up, drafted 2026-10-12. `scripts/results_figure.py` draws its figure from the results table.
- Open, for Dara to decide: a "collided" outcome for the hull contact, and a torque limit on the arm's joints (no sourced value). Do not change the model or run experiments unasked.
- A long run should go in Dara's terminal, since a background job is cut off at two hours.
- `scripts/view.py` must clear `data.qfrc_applied` each step, as `run_trial` does. Any new stepping loop needs the same line or the latch force accumulates.
- When investigating a failure, log contact forces and kinetic energy before explaining it.
- More than one Claude Code session has edited this repository at once before. Check `git status` and `git log` before editing.
