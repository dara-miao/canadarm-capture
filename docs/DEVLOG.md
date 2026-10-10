# Build log

Dated entries, newest last. Each one records what was built, why, what the checks showed, and what went wrong.

## 2026-10-09 to 10 · Choosing the project

**Goal.** A physics simulation project for a portfolio aimed at physical AI.

**How the idea changed.**

1. Started as a from-scratch differentiable simulator in PyTorch. Dropped before any code was kept.
2. Refocused on contact-rich manipulation after reading that insertion, grasping, and tactile tasks "depend on accurate contact geometry, friction, compliance, actuator behavior, and tight tolerances".
3. Switched from building an engine to composing existing tools, after reading how NVIDIA's developers assemble simulations from Omniverse libraries, Newton, and MuJoCo.
4. Checked what runs on a MacBook with no NVIDIA GPU:
   - Runs: MuJoCo, Newton (CPU only), OpenUSD, the MuJoCo and URDF to USD converters, the USD and SimReady validators.
   - Does not run: ovrtx, ovphysx, ovstage, ovstream, ovui, Isaac Sim.
5. Rejected a generic arm pick-and-place as too ordinary. Chose to reconstruct a real operation: Canadarm2 capturing a free-floating cargo vehicle.

**Borrowed from the Market Street driving demo.** Two ideas, not the content: plan the work as a visual pipeline, and reuse one world for several experiments that each change one thing.

## 2026-10-10 · Milestone 1: zero-g scene

**Built.**

- `models/capture_base.xml`: a 7-joint arm on a fixed base and a free-floating vehicle with a grapple pin, gravity off.
- `capture/scene.py`: builds the model, adds the hollow end-effector wall, and places the vehicle relative to the end effector.
- `tests/test_scene.py`: six sanity checks.
- `scripts/render_scene.py`: still images.

![Wide view](media/scene_wide.png)
![End effector and grapple pin](media/scene_closeup.png)

**Design choices.**

- *Joint layout.* Roll, yaw, pitch at the shoulder, one elbow pitch, then pitch, yaw, roll at the wrist. The three pitch axes are parallel, as on the real arm.
- *Hollow end effector.* MuJoCo collides convex shapes, so the cavity is a ring of 16 boxes around a solid base.
- *Vehicle placement is a function, not a fixed pose.* `place_vehicle(standoff, lateral)` positions the pin relative to wherever the end effector is. Misalignment will later be a perturbation of these arguments, so the experiments get their main knob for free.
- *Position-controlled joints.* Each joint has a position actuator. Gains are invented for now.

**Checks (all pass).**

| Check | Result |
|---|---|
| Gravity is zero; 7 actuated joints plus one free body | Pass |
| Straight-arm reach | 17.6 m |
| Pin placed at the requested offset from the cavity mouth | Exact to 1e-9 m |
| Drifting, tumbling vehicle over 120 s with no contact | Linear momentum constant to 1e-6, angular to 1e-3 (relative) |
| Arm holds the ready pose for 10 s | Within 1e-6 rad |
| Arm follows a 0.1 rad step on every joint | Settles within 5e-3 rad in 30 s |

**What went wrong.** The first build had a 17.2 m arm instead of 17.6 m. I had mis-added the segment lengths, and the reach test caught it. Fixed by lengthening each boom from 7.1 m to 7.3 m.

**Not done yet.**

- Shapes are primitives, not real 3D models.
- All dimensions and masses are approximate (listed in `PLAN.md`).
- No snare, no controller, no contact has happened yet.

**Next.** Milestone 2: a closing mechanism inside the end effector that can hold the pin.

## 2026-10-10 · Milestone 2: snare mechanism

**How the real one works.** Three snare cables inside the end effector close around the grapple shaft, then the mechanism pulls the payload in until the interface is rigid. A NASA report gives the design's misalignment tolerance as ±0.1 m lateral and 0.1 m axial.

**Built.**

- A carriage inside the cavity that slides along the approach axis.
- Three snare bars on the carriage, each sliding inward. Open, they form the triangle inscribed in the cavity, so the opening has a 0.1 m inradius, matching the published lateral tolerance. Closed, they meet around the pin.
- One drive for all three bars, tied together with joint constraints, like the rotating ring that drives the real cables.
- `capture/snare.py`: the grapple timing (close over 2 s, pause 2 s, pull in over 2 s).
- `tests/test_snare.py`: eight checks. `scripts/render_capture.py`: stills and an animation.

![Grapple sequence](media/snare_capture.gif)

| Open, pin 6 cm off-centre | Closed and seated |
|---|---|
| ![Open](media/snare_open.png) | ![Seated](media/snare_seated.png) |

**Scope of this milestone.** The pin starts already inside the cavity, the vehicle starts at rest, and the arm only holds still. Approaching a moving vehicle is milestone 3.

**What went wrong: the first design did not hold.** Closing and centring worked on the first try, but a 100 N pull drew the pin straight out. The logged joint positions showed why. The pin had a ball tip, and when the carriage pulled the bars against it, the ball's curved surface pushed the bars outward, from 7.6 cm of travel back to 6.6 cm, until the ball passed through.

Two changes fixed it, both with a physical justification:

1. *Flat-backed knob instead of a ball.* A flat face pushes back along the pin axis only, so it cannot spread the bars.
2. *Stiff snare drive.* Force limit raised from 300 N to 1,500 N and gain from 2e4 to 1e5 N/m, with 5 kg of reflected inertia on each bar. The real drive is geared and does not get pushed open.

I also put the three bars in one plane. They had been stacked 14 mm apart so they could cross, which loaded the knob off-centre. They do not collide with each other, so one plane works.

**Checks (all pass, 14 in total with milestone 1).**

| Check | Result |
|---|---|
| Open snare, pin 5 cm off-centre | No contact |
| Pin starting 6.3 cm off-centre | Centred to under 5 mm after closing |
| Pull-in | Pin tip at 0.300 m depth: fixture plate seated on the rim |
| 500 N pull-out for 20 s, from three start offsets up to 8.5 cm | Pin does not move (within 2 mm) |
| 2,000 N pull-out (twice the carriage force limit) | Plate unseats by 8 cm to the carriage end stop; pin still caught |
| Snare left open, 100 N pull | Vehicle leaves |

**Side effect.** Two milestone 1 tests assumed seven motors; the model now has nine. Updated the tests.

**Not done yet.**

- Bars are rigid. Real cables wrap and stretch.
- Every snare number (forces, speeds, friction) is invented.
- No angular misalignment has been tested, only lateral.

**Next.** Milestone 3: move the arm to a drifting vehicle and trigger the grapple.

## 2026-10-10 · Milestone 3: approach and capture

**Built.**

- `capture/controller.py`: a three-phase controller.
  1. *Align.* Hold 0.4 m in front of the pin until the end effector is within 1 cm and 1 degree of the pin axis for one second.
  2. *Insert.* Advance along the pin axis at 3 cm/s, still tracking, until the pin tip is 0.25 m inside the cavity.
  3. *Grapple.* Freeze the arm and run the snare sequence from milestone 2.
- `capture/trial.py`: runs one attempt and reports success, the phase reached, the trigger time, and the final pin position and relative speed.
- `scene.py`: the vehicle's start can now be tilted, and given a drift and a tumble.
- `tests/test_capture.py`: five checks. `scripts/render_approach.py`: an animation.

![Approach and capture, sped up](media/approach_capture.gif)

**How the tracking works.** Each step computes where the end-effector mouth should be (on the pin axis, at the commanded standoff, facing the pin) and how fast that point is moving. The error plus the target's own velocity gives a desired end-effector velocity. The damped pseudo-inverse of the arm's Jacobian turns that into joint rates, which are integrated into joint position commands. The arm has 7 joints and the task uses 5 degrees of freedom, because roll about the pin axis is left free.

**One detail that mattered.** The joint servos damp joint velocity, so a steadily moving command lags by the ratio of damping gain to position gain, about one second for the large joints. The controller leads each command by exactly that amount, which turns the servo into one that tracks a velocity reference.

**Success means** the controller finished, the pin tip is within 1 cm of the seated depth and 1 cm of the axis, and the pin is moving less than 2 mm/s relative to the end effector.

**Checks (all pass, 19 in total).**

| Start condition | Result |
|---|---|
| At rest, aligned, 0.6 m away | Captured; snare fired at 27 s, finished at 38 s |
| 5.8 cm off-axis, tilted 2.5 degrees, drifting 7 mm/s, tumbling 0.1 deg/s | Captured; final relative speed 0.2 mm/s |
| Leaving at 30 cm/s | Never grappled; the controller is still approaching at the 60 s limit |
| Tilt and drift setters | Produce exactly the requested pin angle and centre-of-mass velocity |

Each trial takes under one second of computer time for about 38 simulated seconds.

**Observed but not yet tested: a first failure type.** With the vehicle receding at 3 cm/s, the snare fires and catches the pin, but the capture does not seat. At the end the pin is 3 cm short of seated, 3 cm off-axis, and still moving at 5.5 mm/s. The 7-tonne vehicle's momentum keeps pulling on the frozen arm. Call this *caught but not rigid*. Milestone 4 should classify it separately from a clean miss.

**A concern.** With perfect knowledge of the pin and generous joint rates, the controller succeeds on everything short of that case. The experiments will need realistic limits, such as sensing noise and delay and joint rate limits, or the capture envelope will show nothing interesting.

**Not done yet.**

- No sensing model. The controller reads the true state.
- Controller gains, speeds, and limits are invented.
- Only a handful of start conditions tried; no systematic sweep.

**Next.** Milestone 4: a trial harness that samples start conditions, runs many attempts, and classifies each outcome.

## 2026-10-10 · Realism audit and prior work

Before building the trial harness, checked the model against public sources and looked for earlier work on the same problem.

**What matches public data.**

| Item | Public figure | Model |
|---|---|---|
| Arm joints | 7: three shoulder, one elbow, three wrist | Same layout |
| Joint range | ±270 degrees | ±270 degrees |
| Arm length | 17 m (CSA); 17.6 m in other sources | 17.6 m |
| Arm mass | 1,497 kg | 1,500 kg |
| Cygnus diameter | 3.07 m | 3.07 m |
| Cygnus length (Enhanced) | 6.39 m | 6.4 m |
| Cygnus mass | up to 8,050 kg loaded | 7,000 kg |
| Capture method | Vehicle in free drift, thrusters off; three snares close, then rigidize | Same sequence |
| Lateral capture tolerance | ±0.1 m | 0.1 m snare opening |

**What does not.**

- *Appearance.* Everything is cylinders, capsules, and boxes. No NASA or CSA 3D model is used. The station is a grey box.
- *Arm internals.* Segment lengths, mass split, and joint offsets are guesses. The real arm flexes; this one is rigid.
- *Grapple fixture.* Cygnus carries a power and video grapple fixture with a shaft, cam arms, and a target. The model has a rod with a knob, at a guessed position on the hull.
- *Snare.* Rigid bars, not cables. No latches or umbilical after rigidizing. All forces and speeds invented.
- *Control.* Real captures are flown by an operator using camera views of a target. The model is autonomous with perfect knowledge of the pin, and its speeds are unverified.
- *Scenario.* The real capture point is about 10 m from the station. The model starts with the end effector 0.6 m from the pin. No orbital mechanics, lighting, or cameras.
- *Validation.* None against flight or test data.

**Prior work found (three searches, not exhaustive, papers not yet read).**

- Professional and academic simulation of this exact mechanism exists and models the snares as flexible cables: a 2023 multibody dynamics conference paper on real-time simulation of cable-based end effectors, a JAXA study of contact between the snare wires and the HTV grapple fixture, and journal papers on snare-type end-effector cable dynamics.
- An on-orbit operations simulator for Canadarm2 track-and-capture training (arXiv 2002.10594).
- MuJoCo-based space robotics tools: mjorbit (arXiv 2609.08010), SmallSatSim (arXiv 2603.14598), and NASA Johnson's open MuJoCo and ROS 2 tooling.
- No open-source MuJoCo study of Canadarm2 free-flyer capture turned up.

**Takeaway.** The idea is not new and professionals model it at far higher fidelity. What this project can offer is a small, open, reproducible study that runs on a laptop, with its assumptions listed. The cable-snare papers are the obvious place to get realistic parameters and something to compare against.

**Also added.** `scripts/view.py`, an interactive viewer that replays a capture.

## 2026-10-10 · Realism pass, step 1: real 3D models

**Why.** The audit above showed the scene was plain shapes with guessed proportions. Decided to fix realism in three steps before running any experiments: real models, sourced parameters, then the real 10 m starting distance.

**What was available.**

| Source | Model | Used? |
|---|---|---|
| Canadian Space Agency | Canadarm2, two boom halves, 1:100 printable | Yes |
| Canadian Space Agency | Cygnus (Enhanced) body and one solar array, 1:100 printable | Yes |
| NASA 3D Resources | International Space Station, several versions | Not yet |
| NASA 3D Resources | Canadarm2 | Does not exist there (only the Shuttle arm) |

The CSA allows non-commercial reproduction with credit and no implied endorsement. To avoid redistributing the files, `scripts/fetch_assets.py` downloads them from the CSA site into a git-ignored folder and converts them. Without them, the simulation falls back to plain shapes.

**The useful surprise.** Each CSA boom file is made of about 40 separate solid pieces: the boom tube, each joint housing, the end effector, the cameras. That meant two things were possible:

1. Assign pieces to moving links, so the arm articulates with the real model's shapes.
2. Read the joint positions off the pieces. The housings are cylinders, and a cylinder's axis is the joint's axis.

Doing that showed the first arm was wrong in kind, not just in detail. It was a straight chain with every joint on one line. The real arm has offset joints: at each end the pitch housing sticks out sideways from the boom, the yaw housing runs along the boom direction 0.72 m off its centreline, and the roll housing and end effector sit another 0.72 m further out. The two booms lie side by side when folded.

**Rebuilt.**

- `models/capture_base.xml`: the arm, with every joint placed from the measured positions. All arm bodies share one assembly frame and each joint has its own position and axis, which avoids chaining seven hand-computed transforms.
- `capture/geometry.py`: the measured offsets.
- `scene.py`: `build_model(meshes=...)` swaps the meshes in for the stand-in shapes. A new ready pose, found by inverse kinematics.
- Vehicle: collision shape is now two cylinders matching the cargo and service modules, and the grapple pin moved to the service module where the model shows a small fixture.

![Scene with real models](media/scene_wide.png)
![End effector approaching the grapple pin](media/scene_closeup.png)
![Approach and capture, sped up](media/approach_capture.gif)

**Kept simple on purpose.** The meshes are appearance only. Collisions still use the cylinder-and-box shapes, now hidden. A test confirms the masses, inertias, and number of colliding shapes are identical with and without meshes.

**What the new geometry broke, and what that showed.**

1. *The pull-out test failed.* It pulled the vehicle through its centre of mass. With the pin now on the service module, 2.5 m from the centre of mass, a 500 N pull is also a 1,200 N m lever on the fixture. The seated plate, held by a 1,000 N pull-in on a 0.24 m rim, cannot resist that, and the vehicle pried itself loose. This is physically right, and the real end effector has latches for exactly this after pull-in. The test now pulls along the pin, which is what it was meant to check. The lever effect is recorded as a risk for defining a rigid capture.
2. *The momentum check needed a looser tolerance* for linear momentum (1e-4 instead of 1e-6), because the vehicle's body origin is now 2 m from its centre of mass.
3. *The reach test no longer made sense* for a folded zero pose. Replaced with checks on boom length, axis directions, and the ready pose.

The approach and capture tests passed unchanged on the new arm.

**Checks.** 21 pass.

**Not done in this step.**

- The station is still a grey box. NASA's free station model loads, but it is low-detail and untextured, and attaching the arm to it properly needs a real attachment point.
- The solar arrays and the arm's links do not collide with anything.
- Joint positions come from bounding boxes of a simplified printable model, not from engineering drawings.

## 2026-10-10 · Realism pass, step 1 continued: the station

**Built.** NASA's International Space Station model (B) replaces the grey box. `scripts/fetch_assets.py` downloads it from NASA's 3D Resources repository, drops a few stray discs that sit far from the station in the source file, scales it, and splits the solar arrays from the rest so they can be coloured.

![Station with the arm and Cygnus](media/scene_station.png)
![Arm mounted on the forward node](media/scene_wide.png)

**Working out the model.** The file has no units and no module names; its meshes are grouped by material, not by module.

- *Scale.* The truss spans 45.6 model units against a real 108.5 m, giving 2.38. Module radii give 2.1 to 2.3. Used 2.35.
- *Which way is down.* The truss sits on one side of the module axis. On the real station the truss is on the space-facing side, so the opposite side faces Earth.
- *Which end is forward.* Cross-sections along the module axis show where the two side-mounted laboratories (Kibo and Columbus) attach. That is the forward node, Harmony.

**What went wrong.** The first placement had forward and aft swapped. I misread which way a rendered view was facing, and the arm ended up floating a metre off the Russian segment. The render made the mistake obvious. Fixed by measuring cross-sections instead of reading the picture.

**Placement.** The arm's base sits on the Earth-facing side of Harmony, and the vehicle is captured about 9 m below it. Cygnus is captured roughly 10 m below the station, so the direction is right. The exact fixture the real arm stands on for these captures is not sourced.

**Limits.**

- The model is low-detail and untextured, and its US modules are about 15% narrower than the real ones at this scale.
- The station is scenery. Nothing collides with it.

**Checks.** 21 pass. The station adds no mass or collision shapes.

## 2026-10-10 · Realism pass, step 2: sourced parameters

**Goal.** Replace invented numbers with published ones wherever a source gives them.

**What could be read.**

| Source | Access | Useful? |
|---|---|---|
| Daniell and Sachdev (1982), the design paper for the Shuttle arm's end effector | Full text (scanned PDF with a text layer) | Yes, the main source |
| Arbatani, Kövecses, and Teichmann (2023), real-time simulation of the Canadarm2 end effector's cables | Two-page extended abstract | For method and context |
| Canadian Space Agency comparison table | Web page | Arm speeds and dimensions |
| Uyama et al. (2009), snare contact with the HTV grapple fixture | Abstract only | No numbers |
| Journal paper on snare cable dynamics | Paywalled | Not read |

The 1982 paper is about the Shuttle arm's end effector, not Canadarm2's. Canadarm2's is a larger descendant of the same three-snare design, so its numbers are a guide and not exact values for this model. The full list is in `PLAN.md` under "Sourced values".

**What changed in the model.**

| Parameter | Was (invented) | Now | Basis |
|---|---|---|---|
| Pull-in force limit | 1,000 N | 3,560 N | Rigidize load in the grapple shaft |
| Pull-in time | 2 s | 10 s | Specification: under 20 s |
| Snare closing time | 2 s | 2 s (kept) | Specification: under 3 s |
| Arm during pull-in | Held rigid | Limp, except wrist roll | "Carried out against a limped arm" |
| Arm tip speed | Uncapped | 0.37 m/s cap | Canadarm2's unloaded speed |

**Three things the sourced numbers exposed.**

1. *The pull-in drive was not delivering its force.* A new test applied the paper's 474.5 N m bending moment, at which the real interface must not separate. The model's joint opened by 1.85 degrees. The drive's position gain was too low to reach its own force limit, so the clamp was about 1,050 N instead of 3,560 N. After raising the gain:

   | Bending moment | Tilt of the pin in the end effector |
   |---|---|
   | 474.5 N m (required: no separation) | 0.000° |
   | 800 N m | 0.009° |
   | 1,200 N m | 10° |
   | 1,627 N m (required: at most 3°) | Pin escapes |

   Separation starts near 850 N m, which is the clamp force times the rim radius (3,560 N × 0.24 m). The model meets the first requirement and fails the second, because it has no cam arms or latches.

2. *The controller failed at the specified capture velocity.* The paper allows the payload to be moving at up to 0.031 m/s at capture. With the vehicle receding at that speed, the model missed. The controller stopped the arm the moment the snare fired, and in the 2 s the snare takes to close the pin backed out 6 cm, past the snare. The controller now keeps tracking until the snare has closed. Captures then succeed at 0.031 m/s and 0.06 m/s in all three directions.

3. *There is no reach limit.* At 0.122 m/s receding (the paper's impact design case, not a capture requirement), the arm chases the vehicle to the edge of its workspace and the controller misbehaves. Logged as a risk; the trial harness needs an out-of-reach abort.

**From the 2023 abstract.** The professional approach models each snare as 10 flexible cable elements, with the pin attached to a 20,000 kg payload and a 1 ms time step, and names contact tunnelling under high cable tension as the main difficulty. This model's rigid bars avoid that problem by not being cables, which is also its main limitation.

**Checks.** 25 pass, including three new ones tied to published figures: the bending moment and the capture velocity in three directions.

**Still invented.** Listed in `PLAN.md` under "Assumptions still unsourced". The main ones are link masses, servo gains, snare cable tension and friction, and the absence of arm flexibility.

## 2026-10-10 · Realism pass, step 3: the 10 m capture point

**Goal.** Start each attempt the way a real capture starts: the vehicle holding at the capture point, and the arm reaching out to it.

**What is published.** Cygnus stops at a capture point about 10 m from the station (12 m for the larger Cygnus XL), switches its thrusters off, and drifts while the arm grapples it. Nothing I could access gives the distance the arm waits from the grapple fixture beforehand, or the vehicle's leftover drift rates. The one operations paper on Canadarm2's first free-flyer capture (Lucier and Smith, 2010) is restricted.

**Built.**

- `scene.CAPTURE_DISTANCE = 10.0`: the grapple pin's tip starts 10 m from the surface the arm stands on.
- `scene.HOVER_DISTANCE = 2.0`: the end effector starts 2 m short of the pin. This is an assumption.
- A new ready pose for the hover point, and `reset()` now defaults to this start.
- The controller is unchanged. Its first phase already moves the end effector to 0.4 m from the pin before aligning; it now has 1.6 m to cover first.

![Approach and capture, sped up](media/approach_capture.gif)

**Results.** An attempt now takes 60 simulated seconds (41 s to the snare firing), up from 46 s, and 1.2 s of computer time.

| Start condition | Result |
|---|---|
| At rest, aligned | Captured |
| Off-axis, tilted 2.5°, drifting 7 mm/s, tumbling | Captured |
| Moving at 0.031 m/s: receding, approaching, sideways | Captured |
| Tilted 10° | Captured |
| Tilted 15° and 8 cm off-axis | Captured |
| Tumbling at 0.6°/s | Captured |

**What this confirms.** The concern from milestone 3 stands. Everything succeeds, because the controller knows the pin's exact position and velocity and simply lines the arm up with it. A 15° tilt is no test of the snare when the arm removes the tilt before inserting. The experiments will only be informative once sensing is imperfect: noise, delay, and limits on how fast the arm can follow.

**Also read.** Freer et al. (2020), the Canadarm2 training simulator found earlier, is a Unity tool for studying operator workload. It has no contact physics, and a grapple there means coming within 1 m. It does give ground-control latency of 0.3 to 0.5 s each way, which sets a realistic range for the sensing-delay parameter.

**Realism pass summary.**

| Step | Outcome |
|---|---|
| 1. Real 3D models | Arm, Cygnus, and station from CSA and NASA models; arm rebuilt with offset joints |
| 2. Sourced parameters | Pull-in force, timings, limp arm, speed cap; two faults found and fixed |
| 3. Capture point | Pin starts 10 m from the station; arm starts 2 m short |

**Checks.** 26 pass.

**Next.** Milestone 4, the trial harness. It needs an out-of-reach abort and outcome labels: captured, missed, caught but not rigid, never reached.
