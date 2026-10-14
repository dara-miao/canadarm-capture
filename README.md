# canadarm-capture

A MuJoCo simulation of a space station manipulator capturing a free-floating cargo vehicle, used to study one question:

**When a contact-rich simulation gives a result, how do you tell whether it is physics or an artefact of how contact was modelled, and which modelling choices is the result most sensitive to?**

[![The station, the approach, an x-ray view of the snare closing, then the collision shapes the solver uses as the fixture is pulled in and latched](docs/media/capture_shapes.gif)](docs/media/capture_shapes.mp4)

One simulated capture in 14 seconds: the approach, an x-ray view of the snare closing, then the collision shapes the solver actually uses while the fixture is pulled in and latched. Click for the full video.

## Why this project

I wanted a contact-rich task with real consequences. Canadarm2 capturing a Cygnus cargo vehicle is one: the target has a mass of seven tonnes and is in free drift, so in microgravity a light contact in the wrong place pushes it away, next to a crewed station.

Canadarm2 performs this capture routinely so I chose it to see whether I could reconstruct a real operation in simulation, and to learn what a contact-rich simulation has to get right. That matters for physical AI: robots are trained and evaluated in simulation, and contact is where simulators are weakest. With gravity removed, contact is nearly the only thing happening, which makes this a clean case for studying it.

## The model

- A 7-joint manipulator with Canadarm2's joint layout, built from the Canadian Space Agency's geometry.
- A 7,000 kg Cygnus with a grapple fixture: a pin on a base plate.
- A latching end effector that snares the pin, retracts to seat the fixture plate against its rim, and latches.
- A resolved-rate controller that tracks the drifting, tumbling vehicle through a sensor model with delay, update rate, and noise.
- A trial harness that runs batches of attempts from a random seed and classifies each outcome: captured, caught but not rigid, lost, missed, out of reach, or timed out.

Every parameter is recorded as sourced, borrowed, or assumed. The [plan](docs/PLAN.md) lists them and the [research notes](docs/RESEARCH.md) give the source for each.

![The station, the arm reaching out from the forward node, and Cygnus holding at the capture point](docs/media/scene_station.png)

*The scene: the station, the manipulator, and Cygnus at the capture point, 10 m out.*

[![The same capture at a slower pace, without the collision-shape view](docs/media/capture.gif)](docs/media/capture.mp4)

*The same attempt at a slower pace, in the detailed models throughout. Click for the full video.*

## Collision geometry

A physics engine does not collide the detailed meshes it renders. Each body has separate collision geometry, usually a few primitives, and that geometry is the body's surface as far as contact is concerned. If it fills in a hole or rounds off an edge, nothing later in the pipeline restores it.

MuJoCo, like many engines, collides convex shapes only. A convex shape has no dents or hollows, which is not the same as being round: a box is convex. A non-convex object is built as a compound of convex pieces. Each piece is convex; the assembled object does not have to be. The cost is seams between the pieces that the real object does not have.

So the choice of collision geometry is a modelling decision, and a result can depend on it. This project aimed to look at how far results varied.

## My initial failure

The end effector is hollow, so its collision geometry is a compound: a ring of 16 boxes, overlapping at their edges to leave no gaps. The top faces of those boxes also served as the rim the fixture plate seats on.

In a harsh batch, with four times the tested drift and tumble, the model lost 27 of the 30 pins it snared. It seemed as though it was a physical failure mode, and the obvious explanations could be physical ones: residual relative velocity at snare closure, an overpowered snare drive, vehicle momentum absorbed through the snare. But then each was tested and ruled out.

Logging contact forces showed the cause. The vehicle keeps tumbling after the snare closes, so the fixture plate meets the rim tilted. Its edge landed where two boxes overlap. The solver received redundant contacts at one location, and when a third arrived with a different normal it returned forces in the millions of newtons and ejected the vehicle faster than it had arrived. 

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/media/rim-dark.svg">
  <img alt="Line chart of the vehicle's speed in one simulated attempt. With the rim modelled as box tops, the speed jumps from 2 to over 20 cm/s when the fixture plate meets the rim, and the pin is lost. With the rim as a ring of spheres it stays near 2 cm/s and the vehicle is captured." src="docs/media/rim.svg">
</picture>

*Figure 1. One attempt with the rim's collision geometry built two ways. Nothing else differs.*

[![The same attempt rendered in the collision-shape view: the fixture plate lands on the box-top rim and the vehicle is thrown off; on the sphere rim it seats](docs/media/rim_contact.gif)](docs/media/rim_contact.mp4)

*The same attempt as a film, in the view the solver sees. Click for the full video, which shows both rims.*

Replacing that one surface with a ring of spheres, each giving a single contact with a single normal, took captures from 3 of 30 to 30 of 30. It also reversed an earlier sensitivity result: a controller change that had appeared to double the failure threshold turned out to have no effect at all.

The mistake is an easy one to make. Overlapping the pieces of a compound to close gaps is the natural thing to do. But the issue is that a surface built for one purpose ends up carrying a load it wasn't made for.

## Experiments

Two experiments on the corrected model. Each condition changes one factor and reruns the same 240 attempts (four drift speeds, 30 scenarios each, two seeds), so outcomes are compared attempt by attempt. The drift speeds run from 4 to 16 cm/s, up to five times the 3.1 cm/s the Shuttle end effector was required to capture at, so that failures occur. The baseline captures 110 of 240, and nearly all of the rest end with the arm unable to reach a receding vehicle before the controller gives up. Including pilots, the project has run more than 12,000 simulated capture attempts.

**Experiment 1: collision geometry and the solver.** The same object with different collision geometry: the rim as box tops, or as 16, 32, or 64 spheres; the cavity wall as 8, 16, or 32 boxes. Four numerical settings were varied alongside: a time step four times finer, doubled contact stiffness, the constraint solver (Newton, CG, or PGS), and the friction cone (pyramidal or elliptic).

**Experiment 2: numbers not known exactly.** Each parameter without a reliable source was treated as a measurement with an uncertainty and moved across a plausible range: the friction coefficient at two separate contacts (0.1 to 0.8), the joint rate limit, joint back-drive friction, observation delay, and the two numbers that decide when the controller gives up, its reach threshold and its time limit.

**Guardrail:** a set of checks that runs on every attempt and flags anything non-physical. An unstable step, a contact force above anything the actuators can apply, a vehicle leaving a contact faster than it arrived, interpenetration beyond 1 cm, a joint driven past its limit. Ideally it never fires. Validated against the original rim, where 50 attempts were known artefacts, it flagged all 50.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/media/results-dark.svg">
  <img alt="Bar chart of how many of 240 attempts changed outcome when one thing was changed. Sound changes to how contact is represented changed at most 7, near a noise floor of 3. The old box-top rim changed 79. Physical unknowns changed up to 180." src="docs/media/results.svg">
</picture>

*Figure 2. Experiment 1 in blue, experiment 2 in orange. Each bar is one factor changed from the baseline, on the same 240 attempts.*

Two conditions calibrate the method. A perturbation with no physical meaning, moving the initial position by 0.001 mm, changes 3 outcomes of 240: that is the noise floor. And the snare drive's force limit, included as a negative control, changes 2.

## Results

1. **With sound collision geometry, the exact choice barely matters.** Sphere count, box count, time step, contact stiffness, constraint solver, and friction cone each changed at most 7 outcomes of 240, close to the noise floor of 3.
2. **The uncertain physical parameters matter far more.** The joint rate limit changed 180 outcomes; friction where the fixture seats on the rim, 96; observation delay, 68.
3. **One unsound collision geometry mattered as much as real physics.** The original rim changed 79 outcomes, more than all but two of the physical parameters. From the outcome counts alone it was indistinguishable from a real effect. Only the guardrail separated them.
4. **The most influential parameter is an assumed one.** No source gives the joint rate limit. The best-sourced parameter in the model, the rigidizing force, had no effect across its range.
5. **Friction matters at one contact only:** where the tilted fixture plate has to slide flat on the rim, not where the snare holds the pin.
6. **When the controller gives up decides labels, not captures.** Halving or doubling its reach threshold changed 17 outcomes but not one capture: only which failure an attempt was called. Doubling the time limit to 360 s gained 3 captures, because the attempts that run out of time are ones where the vehicle leaves the arm's reach. Halving it to 90 s lost 24, 18 of them attempts that the limit itself cut off in the middle of the grapple sequence.

## What transfers to other simulations

- Collision geometry is a modelling choice. Give every load-bearing contact its own simple surface, with no seams where the contact lands.
- Test contacts tilted and off centre, not only in the nominal configuration.
- Run a guardrail on every trial for forces no actuator could produce and for kinetic energy appearing from nowhere. Outcome labels do not reveal them.
- When a failure appears, log contact forces and energy before explaining it.
- Measure the noise floor with a perturbation that should do nothing, so that "no effect" has a size.
- Treat every assumed parameter as a measurement with an uncertainty, and sweep it.
- Keep a negative control.

## Limitations

This is simulation only and has not been validated against flight data. The controller is my own, and the snare is modelled as rigid bars where the real one uses cables. The guardrail still flags two edge cases on the corrected model, both traced to those simplifications; neither changes a capture count. Details are in the [build log](docs/DEVLOG.md).

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

## License

The code and documentation in this repository are under the [MIT License](LICENSE). The downloaded 3D models are not covered by it; they remain under the Canadian Space Agency's and NASA's own terms.
