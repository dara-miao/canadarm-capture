# canadarm-capture

A simulation of a space station's robot arm catching a free-drifting cargo ship, built to answer one question:

**When a contact-rich simulation gives a result, how do you tell whether it is physics or an artefact of how contact was modelled, and which modelling choices does the result depend on?**

[![Preview of the simulation: the station, the approach, the snare closing, and the vehicle held](docs/media/preview.gif)](docs/media/preview.mp4)

A simulated capture at four times real speed. Click for the full-size video.

## Why this scenario

I wanted something harder than a robot arm on a desk picking up a mug, and real. Canadarm2 catching a Cygnus cargo ship is that: the target weighs seven tonnes and floats free, so in zero gravity a touch in the wrong place pushes it away, next to a crewed station.

This project solves no problem for the space industry. Canadarm2 does this routinely. I chose it because zero gravity leaves contact as nearly the only thing going on, which makes it a clean place to see what a simulator's contact model is doing. That matters for physical AI: robots are trained and tested in simulation, and contact is the part simulators find hardest.

## What is in the model

A 7-joint arm built from the Canadian Space Agency's Canadarm2 geometry, a 7-tonne Cygnus with a grapple pin, and an end effector that snares the pin, pulls it in, and latches, in MuJoCo with gravity off. A controller lines the arm up with the drifting, tumbling ship through a sensor model with delay and noise. One command runs a batch of attempts and labels how each one ended.

Every number is listed in the [plan](docs/PLAN.md) as sourced, borrowed, or guessed, and the [research notes](docs/RESEARCH.md) say where each comes from.

![Station, arm, and Cygnus](docs/media/scene_station.png)

## A failure that was not physics

In harsh conditions the model lost most of the pins it snared: 27 of 30. It looked like a real failure mode, and I wrote down three physical explanations for it. All three were wrong.

Logging the contact forces showed what was happening. The ship keeps tumbling after the snare closes, its fixture plate tilts onto the end effector's rim, and at that moment the contact force jumped to as much as 2.3 million newtons and threw the ship off faster than it had arrived. A contact cannot add energy. The solver was failing on one pair of shapes: the rim was the tops of 16 overlapping boxes, and the plate's edge touched two of them in the same place.

Rebuilding that one surface as a ring of spheres took captures from 3 of 30 to 30 of 30. It also overturned the conclusion I had drawn about which parameter mattered most.

Nothing in the results had flagged it. The outcome labels looked like any other result.

## The experiments

Three experiments on the fixed model. Each condition changes one thing and runs the same 240 attempts, so attempts can be compared in pairs.

- **A. Can a non-physical result be caught?** Five checks run on every attempt: an unstable step, a contact force no part of the machine could produce, a ship leaving a contact faster than it arrived, shapes overlapping by more than a centimetre, and a joint pushed past its stop. On the old rim, where 50 attempts were known artefacts, they flagged all 50.
- **B. Does the result survive a change of representation?** Change how an object is described without changing the object: the shape of a contact surface, the time step, the contact stiffness.
- **C. Which physical unknowns matter?** Move each number that is not known exactly across a plausible range.

![What moved the result](docs/media/results.svg)

Two conditions are there to keep the method honest. Nudging the start by a thousandth of a millimetre changes 3 outcomes of 240: that is what "no effect" looks like. And the snare's drive force, which I expected to do nothing, changed 2.

## What I found

1. **Once the contact is sound, how it is represented barely matters.** Sphere count, box count, time step, and stiffness each changed at most 7 outcomes of 240, close to the noise floor of 3.
2. **The physical unknowns matter far more.** How fast the arm's joints may turn changed 180 outcomes; friction where the fixture seats, 96; a stale view of the pin, 68.
3. **One unsound representation mattered as much as real physics.** The old rim changed 79 outcomes, more than all but two of the physical unknowns, and from the outcome counts it looked like any other result. Only the checks told them apart.
4. **The number that matters most is one I invented.** The joint rate cap is not in any source I could find. The best-sourced number in the model, the pull-in force, made no difference at all.
5. **Friction matters at one contact only:** where the tilted fixture has to slide flat on the rim, not where the snare holds the pin.

## What I would carry to another simulation

- Log contact forces and energy before explaining a failure. I wrote three explanations before I did, and one replay settled it.
- Check every run for things that cannot happen. Outcome labels do not show them.
- Measure the noise floor with a change that means nothing, so "no effect" has a size.
- Change the representation, and see whether the result survives.
- Keep a control you expect to do nothing.
- Give every guessed number a range, as you would a measurement in a physics lab, and move it.

## What is still wrong, and what limits this

The checks still flag attempts on the fixed model, and both causes are traced:

- When an approach fails, the end effector can run into the ship's hull, and the arm keeps pushing with up to 200,000 N m, because its motors have no torque limit. The contact is behaving; the motor is impossible.
- At low friction the pin's knob wedges between the snare's rigid bars with up to 90 kN on each. Real cables would give.

Neither changes a capture count. Both come from assumptions I had listed from the start without knowing what they did.

The limits are plain. This is simulation only, never compared with flight data. The controller is invented, and the largest effect I found is a property of it. The snare is rigid bars, not cables; the latches are a force; the cams that straighten the real fixture are a flat plate on a ring of spheres. The experiments use two random seeds and change one number at a time. And the cause of the original contact failure is the likely one, not a proved one.

## More

- [Build log](docs/DEVLOG.md): what was built, what it showed, and what went wrong.
- [Plan](docs/PLAN.md): the question, the experiments, every decision and assumption.
- [Research notes](docs/RESEARCH.md): the real operation, the sources, and where each number comes from.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m capture.batch --n 60 --seed 0
```

That runs with plain stand-in shapes. To use the real 3D models, fetch them once (about 10 MB, from the Canadian Space Agency and NASA):

```bash
.venv/bin/pip install -e ".[assets]"
.venv/bin/python scripts/fetch_assets.py
```

For a starry background in place of plain black (an invented sky, generated locally):

```bash
.venv/bin/python scripts/make_sky.py
```

To watch a capture interactively on macOS (add `--shapes` to see the collision shapes instead of the 3D models):

```bash
.venv/bin/mjpython scripts/view.py
```

To rerun the experiments (two to three hours on eight cores; delete `results/experiments` first to start from nothing):

```bash
.venv/bin/python experiments/run_experiments.py
```

Runs on CPU. Developed on an Apple Silicon Mac with MuJoCo 3.15.

## Credits

3D models of Canadarm2 and Cygnus: Canadian Space Agency. 3D model of the International Space Station: NASA. They are downloaded from the agencies' own sites, not stored here, and used for non-commercial purposes. This project is not associated with or endorsed by the Canadian Space Agency or NASA.

## How this was built

I directed the project and made the design decisions; the code was written with Claude Code. The [build log](docs/DEVLOG.md) records each step, including the approaches that failed.
