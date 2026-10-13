# Build log

What was built, what it showed, and what went wrong, in order. Trimmed on 2026-10-12 to the parts that matter; the full day-by-day version is in the git history.

## Why this project

I wanted a real operation with real consequences, where making contact is the whole difficulty. Capturing a spacecraft is that. The target weighs seven tonnes and floats free, so in zero gravity a light touch in the wrong place pushes it away, right next to a crewed station.

I also wanted to push myself: to see whether I could replicate a real operation in simulation, and to learn along the way everything a contact-rich simulation has to get right. My interest is physical AI, where robots are trained and tested in simulation, and contact is the part simulators find hardest.

## 2026-10-10 · Building the model

**The world.** A 7-joint arm on a fixed base and a free-floating vehicle with a grapple pin, gravity off, in MuJoCo. MuJoCo collides convex shapes only, so the hollow end effector is a ring of 16 boxes around a solid base. Checks: a drifting, tumbling vehicle with nothing touching it keeps its momentum, and the arm holds and follows commands.

**The snare.** Three bars on a sliding carriage close around the pin, then the carriage pulls the fixture in until its plate sits on the end effector's rim. The bars are rigid; the real snare is three cables.

*What went wrong.* The first design did not hold. The pin had a ball tip, and when the carriage pulled the bars against it the ball's curve pushed the bars apart until it slipped through. Fixed with a flat-backed knob, which cannot spread the bars, and a stiffer drive. This was the first time a choice of collision shape decided the result.

**The controller.** Three phases: line up 0.4 m in front of the pin, insert at 3 cm/s while tracking, fire the snare. Tracking turns the pin's position and velocity into joint rates through the arm's Jacobian. It leaves roll about the pin free, since the pin is symmetric.

**Real geometry.** The Canadian Space Agency's printable Canadarm2 model is made of about 40 separate pieces, so the joint positions could be read off the joint housings. That showed the first arm was wrong in kind: the real arm's joints are offset from the booms, not in a line. The arm was rebuilt from the measured positions. Cygnus and the station also use CSA and NASA models. The detailed models are appearance only; collisions keep the simple shapes.

**Sourced numbers.** Two design papers for the Shuttle arm's and Canadarm2's end effectors supplied the pull-in force (4,893 N), the latch force (64,054 N), the timings, and the misalignments the mechanism was tested at. The research notes say where every number comes from.

Fitting the sourced numbers exposed two faults:

1. The pull-in drive was not delivering its force. Its gain was too low to reach its own limit, so the clamp was about 1,050 N instead of 3,560 N. Found by applying the paper's bending load and watching the joint open.
2. The controller stopped the arm the moment the snare fired. In the 2 s the snare takes to close, a receding pin backed out 6 cm. The arm now keeps tracking until the snare has closed.

**The start.** Each attempt begins with the pin 10 m from the station, the published capture distance, and the end effector 2 m short of it, which is an assumption.

**The trial harness.** One command runs a batch of attempts from a random seed and labels how each ended: captured, caught but not rigid, lost, missed, out of reach, or timed out. The controller sees the pin through a sensor model with delay, update rate, and noise. "Captured" means seated, latched, and still held after a 1,627 N m bending load.

*What went wrong.* With noisy measurements the controller hovered until it timed out, because it tested its alignment tolerance against every raw reading. A small estimator that averages the readings fixed it.

**First batches.** 60 attempts each.

| Batch | Captured |
|---|---|
| Drift to 3.1 cm/s, tumble to 0.5 deg/s, perfect sensing | 60 |
| The same, with 0.5 s delay and centimetre noise | 60 |
| Four times the drift and tumble | 3 |

In the harsh batch 27 attempts were "lost": the snare closed on the pin and the pin later escaped.

## 2026-10-10 to 11 · The lost pins

**Three explanations, all wrong.** Small pilot experiments on the harsh batch produced three accounts of why snared pins were lost, each written down as it came:

1. The snare closed on a pin still moving relative to the end effector. Wrong: perfect sensing cut that speed from 5.8 to 0.9 cm/s and 26 were still lost.
2. The snare's drive was overpowered. Wrong: halving or doubling its force changed nothing.
3. The vehicle's momentum had to be absorbed through the snare. Wrong: before the pin left, the bars carried little more than the pull-in drive's own force.

The pilots also produced a headline: letting the arm go limp as soon as the snare closed doubled the drift speed at which capture failed, from 6 to 12 cm/s.

**What it actually was.** Logging contact forces and the vehicle's motion for every attempt showed the same sequence in all 50 lost attempts:

1. The snare closes with the pin nearly on axis.
2. The vehicle keeps tumbling. Three bars round a pin hold a point; they do not stop rotation.
3. About 6 s later, at 5 to 12 degrees of tilt, the fixture's plate meets the end effector's rim.
4. Within hundredths of a second the contact force reaches between 73 kN and 2.3 MN, and the vehicle is thrown off at a median 56 cm/s, having arrived at about 7.

Step 4 is not physics. A contact cannot give a vehicle more energy than it had. Logged step by step, the contact behaved for a tenth of a second (578 N at 3.3 mm of overlap), then jumped to 245 kN on the single step when a third wall box came into contact, with no jump in overlap. The wall boxes overlap at their edges, so the plate's edge was touching two of them in the same place. That is the likely cause; it was not proved.

**The fix.** The plate now seats on a ring of 32 spheres set into the rim, one contact and one direction each. Nothing else changed. A replay of the failing attempt is now a test.

| Harsh batch, of 30 snared | Box-top rim | Sphere rim |
|---|---|---|
| Captured, default arm | 3 | 30 |
| Captured, arm limp from snare closure | 7 | 30 |
| Largest force at the rim before latching | up to 2.3 MN | about 3 kN |

The plate still tilts up to 14 degrees onto the rim. Pull-in now levers it flat.

**The mistake, plainly.** It was in how the model was built, by Claude Code, at the very first milestone.

- The end effector has to be hollow so the pin can go in. The simulator only collides shapes with no hollows, so the tube was built from 16 flat boxes standing in a ring.
- To leave no gaps between them, each box was made slightly too wide, so neighbours overlap at their edges.
- Those boxes were meant to be the tube's wall. But their top faces also became the rim that the fixture plate lands on. Nobody chose that; it came for free.
- When the plate landed flat, it rested on all 16 tops evenly and nothing went wrong. Every test checked a flat landing.
- When the plate landed tilted, its edge came down on a place where two boxes overlap. The simulator saw two contacts at the same spot, and when a third arrived at a different angle it could not work out a sensible answer and returned an enormous force.

**Why this is easy to do.**

- Building a hollow thing from overlapping pieces is the standard approach, and overlapping them to close the gaps is the obvious next step.
- A surface built for one job quietly ends up doing a second one.
- Tests check the case the builder had in mind, here a flat landing, and not the awkward one.
- The result had a believable name. "Lost" sounds like something a real capture could do, so it got explained instead of questioned.

**The rule from now on.**

- Any surface that takes a load gets its own simple shape, with no seams or overlaps where the contact lands.
- Test contacts at an angle and off centre, not only in the tidy case.
- Check every run for forces the machine could not make and for motion that needs energy from nowhere.
- When something fails, log the forces before explaining it.

**What the fix undid.** The pilot headline went with it. On the fixed model, going limp at closure does nothing at all, and the numbers that matter are different ones. The sensitivity ranking itself had been an artefact of one collision surface.

**What went wrong.** Three explanations were written before anyone logged a contact force. The check that settled it, whether the vehicle gained energy, took one replay.

## 2026-10-11 · Stepping back

I stopped the work to ask what problem this solves. For the space industry, none: Canadarm2 does this routinely, with a forgiving mechanism, a cooperative target, and a trained operator. The work had also been running ahead of my own understanding of it.

The most useful thing the project had produced was the lost-pin episode. So the question changed to one that carries beyond this scenario:

**When a contact-rich simulation gives a result, how do you tell whether it is physics or an artefact of how contact was modelled, and which modelling choices is the result most sensitive to?**

**What I learned about collision shapes.** A simulator collides simple hidden shapes, not the models it draws, and that shape is the object's surface as far as physics is concerned. Convex means no dents or hollows, not round. Each piece has to be convex but the object built from them does not: an open box made of five slabs is hollow. What that costs is seams, edges and overlaps the real object does not have, and my lost-pin bug was at one. Needing convex shapes is a property of the engine, not of physics. Sources are in the research notes.

This model has now changed a collision shape three times (the cavity from boxes, the pin's tip from a ball to a disc, the rim from box tops to spheres) and the result changed each time.

**A viewer bug.** The interactive viewer's own loop never cleared the latch force between steps, so in the viewer only, the force piled up until the simulation went unstable. Batches and tests were not affected. Another result that came from how the simulation was run, not from the model.

## 2026-10-11 to 12 · The experiments

Two experiments on the fixed model, with a guardrail running on every attempt. Every condition changes one thing and runs the same 240 attempts: drift at 4, 8, 12, and 16 cm/s, 30 scenarios each, two seeds, tumble up to 2 deg/s. The baseline captures 110 of 240. About 7,000 attempts were simulated for these, and more than 10,000 in the project counting the pilots.

### The guardrail

Not an experiment: an alarm on every attempt, which ideally never fires. Every attempt is checked for five signs: an unstable step, a contact force on the vehicle over 150 kN (about twice what the machine can apply), the vehicle leaving a contact faster than 1.5 times its fastest speed before, shapes overlapping by more than 1 cm, and a sliding joint 5 mm past its stop.

Tested on the old rim, where 50 attempts are known artefacts: all 50 flagged.

### Experiment 1: collision geometry

| What changes | Captured, of 240 | Outcomes changed |
|---|---|---|
| Baseline | 110 | |
| Nothing meaningful: start nudged 0.001 mm | 111 | 3 |
| Rim as box tops | 33 | 79 |
| Rim as 16 or 64 spheres | 110, 110 | 2, 0 |
| Cavity wall as 8 or 32 boxes | 112, 112 | 5, 7 |
| Time step 0.5 ms | 110 | 3 |
| Contact twice as stiff | 110 | 7 |

A meaningless change flips 3 outcomes. That is the noise floor. Every sound change of representation is within a few attempts of it. The old rim is not.

### Experiment 2: which physical unknowns matter?

| Number | Range | Captured at each end | Outcomes changed | How it fails |
|---|---|---|---|---|
| Joint rate cap | 0.015 to 0.06 rad/s | 21, 199 | 180 | A slow arm times out before it can fire |
| Friction at the rim | 0.1 to 0.8 | 111, 14 | 96 | At 0.8 the fixture is caught but not pulled rigid |
| Observation delay | 0.5, 1.0 s | 101, 55 | 68 | The snare fires and misses |
| Joint back-drive friction | 100 to 400 N m | 111, 101 | 17 | At 400, more caught but not rigid |
| Friction at the pin | 0.1 to 0.8 | 111, 108 | 8 | |
| Snare drive force (control) | 750 to 3,000 N | 108, 110 | 2 | Expected to do nothing, and did |

Pull-in force, vehicle mass, a 1 ms time step, and friction changed everywhere at once were also run and made no difference worth keeping; the plan records them.

- One number dominates, and it is invented: the joint rate cap. It is also the first thing the research could not find.
- Friction matters at one contact only, the rim, where the tilted plate has to slide flat.
- The best-sourced number in the model, the pull-in force, makes no difference over its range.

### The answer, for this model

| | Most outcomes changed, of 240 |
|---|---|
| Noise floor | 3 |
| Any sound change of representation | 7 |
| The old box-top rim | 79 |
| The physical unknowns | 180 |

Once the checks pass, how contact is represented moves the result about as much as noise, and the physical unknowns move it more than twenty times as far. But one unsound representation moved it as much as the second-largest physical effect, and from the outcome counts alone it looked like any other result. Only the checks told them apart.

### What the guardrail still flags

The fixed model is not clean. The checks flag 17 of the 240 baseline attempts, and 105 at pin friction 0.1. Both were traced by replaying attempts and printing what was touching what.

- *The end effector runs into the hull.* In 16 of the 17, while the arm is still lining up and the pin is 0.3 to 6 m off target, the end effector touches the vehicle's hull and the arm keeps pushing. Joint torque goes from about 200 N m to as much as 200,000, and the contact force to 5 MN. The arm's motors have no torque limit and the controller does not know the hull is there. The contact is behaving; the motor is impossible. These attempts had already failed.
- *The knob wedges between the bars.* At low pin friction the pin's knob slides into the narrowing gap between two rigid snare bars, which squeeze it with 48 to 90 kN each, ten to twenty times the pull-in force. Real cables would give. These attempts still end captured.

Neither changes a capture count, so the results above stand. Both come from assumptions the plan had listed all along: no torque limits, and rigid bars for cables. Listing an assumption is not the same as knowing what it does.

## What limits all of this

- Results describe this model. Nothing here has been compared with flight data or hardware.
- The controller is invented, and the largest effect found is a property of it.
- The snare is rigid bars, the latches are a force, and the cams that remove tilt on the real fixture are a flat plate on a ring of spheres.
- Two seeds, one family of scenarios, and each number changed alone.
- The cause of the original contact failure is a likely one, not a demonstrated one.

## Open

- A "collided" outcome for when the end effector touches the hull before firing.
- A torque limit on the arm's joints. No sourced value.
- The write-up.
