# Research notes

What we know about capturing a free-flying spacecraft with Canadarm2, where each fact comes from, and how far to trust it. This sits beside the [plan](PLAN.md) (what we intend to build) and the [build log](DEVLOG.md) (what we built and what happened).

The rule for this project: understand the real operation before running experiments or writing about them.

## How to read this

Every claim carries one of four labels.

| Label | Meaning |
|---|---|
| **Read** | Taken from the source itself, which was opened and read for this project |
| **Read (summary)** | The source was opened, but through a tool that returns a summary with quotations, not the raw text. Good for the specific points checked; not a full reading |
| **Reported** | Came from a secondary summary (a Perplexity search) and has not been checked against the source |
| **Assumed** | No source. A value chosen for the model |
| **Disputed** | Sources disagree |

Perplexity searches were mine. Sources were opened and checked with Claude Code, so "Read" means the source was opened for this project, not that I have read every page myself.

Numbers are given exactly as the source prints them, with its units. Wording is mostly paraphrased; short quotations are kept where the exact words matter, with the author named. Long passages are not copied, because this repository is public and most of these papers are under copyright.

A number being published does not make it a hardware specification. Several values below are inputs that a modelling paper chose, or starting guesses for a fitting procedure. The "what it is" column says which.

## 1. The operation in plain words

A cargo ship that cannot dock by itself flies up underneath the station and stops at a *capture point*, about 10 m away (12 m for the larger Cygnus XL). Its guidance has matched its motion to the station's, so it appears to hang still. It then switches its thrusters off. This state is called *free drift*.

The arm's operator, an astronaut at a workstation in the station's Cupola, flies the end of the arm toward a fixture on the ship's side: a *grapple fixture*, with a shaft sticking out of a target plate. The arm's hollow end, the *Latching End Effector* (LEE), goes over the shaft. On command the LEE runs an automatic sequence:

1. **Snare.** Three cables inside the LEE close around the shaft and centre it.
2. **Rigidize.** A carriage pulls the cables back, drawing the fixture against the LEE's face. Cams on the fixture remove tilt, then roll.
3. **Latch.** Four latches clamp the interface with much higher force, and connect power and data on fixtures that have connectors.

The arm then carries the ship to a port and holds it there while it is bolted on. That second step is *berthing*. Capture and berthing are separate events.

Three clarifications matter for the model:

- **Free drift is not tumbling.** Nothing mechanically restrains the ship, but its approach was carefully controlled up to that moment. Leftover motion is small. (How small is one of the open questions.)
- **A person flies the arm.** The real capture is manual, with the LEE's sequence automated. This project's controller is autonomous, which is a different thing.
- **Cygnus is a cooperative target.** It holds position and presents a fixture built for the purpose. Capturing debris or a dead satellite is a much harder problem and the literature on it does not describe Canadarm2 operations.

## 2. Ideas worth having straight

**Impulse.** A contact force acting for a short time changes momentum: the ship's velocity changes by the impulse divided by its mass. If the contact is off-centre it also changes the ship's spin, by the impulse's lever arm about the centre of mass. That is why a clumsy touch on a fixture mounted on the side of a ship both pushes it away and starts it turning.

**Compliance versus damping.** Something that gives under load spreads a contact over a longer time and lowers the peak force. But give alone stores energy and hands it back, which is a rebound. Capture needs give *and* energy loss. Making everything soft is not the answer.

**Capture is a race.** Engagement succeeds only if the mechanism finishes securing the target before relative motion takes the opportunity away. Three times are worth keeping apart: how long the pin stays in a catchable position, how long the snare takes to close, and how long pull-in and retention take. This is why leftover motion, sensing delay, and actuator speed interact instead of adding up independently. The model has already shown it: when the arm stopped the moment the snare fired, a receding pin backed out before the snare shut. Christidi-Loumpasefski et al. (2024) make the same point for a different mechanism, where too short a contact means the attachment never forms.

**Limp mode.** One of the arm's non-motion modes. Chang and Marquez (2018) list four: safed, brakes on, standby (motors hold position), and limp, in which the "arm joints are passively compliant". During rigidizing the arm is limp so the LEE can pull itself into line with the fixture instead of fighting the arm.

**A position command is not a force guarantee.** A controller that insists on a position regardless of contact produces whatever force that takes. Contact-rich control (impedance control, hybrid force and position control) shapes how the robot yields. This is the shared ground with manipulation on Earth: in both, success depends on geometry, friction, compliance, and control response together, not on position accuracy alone.

**Collision geometry is a modelling choice.** A simulator keeps two versions of every object: the detailed model that is drawn, and a simpler shape that physics uses for contact. The simulation's idea of an object's surface is the second one. If that shape fills in a hole or rounds off an edge, nothing later in the calculation can put it back.

- *What the detector hands on.* For each contact, a point, a direction (the normal), and a distance or depth. MuJoCo "works with point contacts" (its documentation). The solver then turns those into forces. So a point, an edge, and a flat face can give different contact directions and different outcomes.
- *Two kinds of simplification, easy to confuse.* A rough bounding box is used only to decide which pairs are worth checking (the broad phase). The collision shape itself is what the careful check (the narrow phase) uses, and simplifying that one changes the result.
- *Convex does not mean round.* A shape is convex if a straight line between any two points inside it stays inside. A box with sharp corners is convex. A mug, a tube, and a bowl are not.
- *Why engines like convex shapes.* The standard fast distance algorithm (GJK) asks a shape for its farthest point in a given direction. For a convex shape that is enough to find the distance. For a dented shape those points describe the shape's hull, with the dents filled in.
- *Three ways to represent an object,* from cheapest to most detailed: one simple shape; several convex pieces fixed together (a compound); a full triangle mesh or a distance field. The test for which to use is whether removing a detail would change the contact outcome that matters. More detail is not automatically more accurate or more stable.
- *The restriction belongs to the engine, not to physics.* Some engines collide concave meshes or distance fields directly. MuJoCo does not: its documentation says it "only supports convex geom-geom collisions", replaces a non-convex mesh with its convex hull, and expects hollow objects to be built as a union of convex pieces on one body.
- *Convex pieces, concave whole.* Each piece has to be convex; the object built from them does not. An open box made of five slabs is hollow because no slab fills the inside.
- *The cost is seams.* Where two pieces meet there is an edge or an overlap that the real object does not have, and contact near it can misbehave. This model's lost-pin failure was at one: the plate touched two overlapping wall boxes in the same place.
- *Automatic splitting can erase what matters.* Tools that cut a mesh into convex pieces can still bridge an opening. Wei et al. (2022) built CoACD around exactly that: earlier methods may end up "filling a toaster's slots". On their project page, a drawer handle whose openings survive the split lets a simulated robot open the drawer more often than one whose openings were filled.

*In this model.* The end effector's cavity is a compound: a ring of 16 boxes. The pin's tip was changed from a ball to a flat-backed disc because the snare bars wedged apart on the ball. The rim was changed from the box tops to a ring of spheres because the plate's contact with two overlapping boxes broke the solver. Each was a choice of collision shape, and each changed the result. A natural experiment for the project's question: represent the same surface several ways and see which results survive.

**Where the Earth analogy stops.** On Earth the workpiece is usually held by something. Here the target is free, so contact can send it out of reach. And Canadarm2 stands on a 400-tonne station, unlike a small servicing satellite whose own body moves when its arm does. Papers about free-floating robot bases do not transfer directly.

## 3. Sources

### Read in full

**Walker and Vandersluis (1995).** "Design, Testing and Evaluation of Latching End Effector." Spar Aerospace. 29th Aerospace Mechanisms Symposium, NASA CP-3293, pp. 1-16. [NTRS 19950020841](https://ntrs.nasa.gov/citations/19950020841) (full text is inside the proceedings, [19950020840](https://ntrs.nasa.gov/api/citations/19950020840/downloads/19950020840.pdf)).
The design and test paper for Canadarm2's own end effector, by its builder. The single most relevant source found. It calls the LEE "a descendant of" the Shuttle arm's end effector, with latches added to carry the larger moments of station payloads. Gives requirements, preload forces, and test conditions.
*Caution:* describes an engineering model tested in 1993. Flight units may differ.

**Daniell and Sachdev (1982).** "The Design and Development of an End Effector for the Shuttle Remote Manipulator System." Spar Aerospace. [NTRS 19820015473](https://ntrs.nasa.gov/api/citations/19820015473/downloads/19820015473.pdf).
The same kind of paper for the Shuttle arm's end effector, the LEE's ancestor. Has the fullest statement of capture requirements: tolerances, times, velocities, loads.
*Caution:* a smaller, earlier device (0.34 m diameter, 29.5 kg). Use for the LEE only where Walker and Vandersluis are silent, and say so.

**Honda, Oda, Nakanishi, and Suzuki (2014).** "Contact Dynamics Analysis for HTV Capturing by SSRMS." *Trans. JSASS Aerospace Technology Japan*, vol. 12, no. ists29, pp. Pc_9-Pc_14. [J-STAGE](https://www.jstage.jst.go.jp/article/tastj/12/ists29/12_Pc_9/_pdf).
A multibody simulation of Canadarm2 capturing Japan's HTV, with parameters fitted to telemetry from the first HTV capture. The closest published work to this project. Notably it models the snare wires as rigid rotating rods, which is close to what this project does.
*Caution:* almost every number in it is either an input the authors chose or a starting value for their fitting. The fitted results are shown in plots, not tabulated. It gives the capture date as July 2009; the Canadian Space Agency says 17 September 2009.

**Chang and Marquez (2018).** "Human-Automation Allocations for Current Robotic Space Operations: Space Station Remote Manipulator System." NASA/TM-2018-220042. [NTRS 20200003149](https://ntrs.nasa.gov/api/citations/20200003149/downloads/20200003149.pdf).
Describes who does what during arm operations, including free-flyer capture. The best open description of the procedure.
*Caution:* the authors state they "are not SSRMS operators, designers, or engineers"; it is a human-factors description from observation and interviews. It gives no numerical rates.

**Arbatani, Kövecses, and Teichmann (2023).** "Real-time Simulation of Cable-Based Robotic End Effectors." McGill University and CM Labs. ECCOMAS Multibody Dynamics, Lisbon. [Extended abstract](https://multibody2023.tecnico.ulisboa.pt/prog_MULTIBODY_WEB/MULTBODY2023_ABSTRACTS/ID_243_327_ECCOMAS_MBD_2023_accepted_rev.pdf).
The professional way to simulate the LEE: each snare as 10 flexible cable elements, with cable-to-pin and cable-to-cable contact. Names contact tunnelling under high cable tension as the central difficulty.
*Caution:* a two-page abstract. Its numbers describe the simulation, not the hardware.

**Christidi-Loumpasefski, Yalçın, Delisle, Li, Olivares-Mendez, and Martinez (2024).** "Adaptive Control Scheme for Space Debris Capture in the Presence of Mass and Inertia Uncertainty." University of Luxembourg. *IEEE Access*, DOI 10.1109/ACCESS.2024.3374109. [Author manuscript](https://orbilu.uni.lu/bitstream/10993/60540/1/Adaptive_Control_Scheme_for_Space_Debris_Capture_in_the_Presence_of_Mass_and_Inertia_Uncertainty_preprint.pdf).
A compliant capture device with gecko-adhesive pads, mounted on a CubeSat, for debris. Not Canadarm2 and not a snare. Useful for one idea: capture has a soft phase that must last long enough for the hard attachment to form. In their simulation the true debris mass is 4 kg while the controller first assumes 12 kg. Without adaptation, contact lasts 7 s; with the mass estimated during contact and gains updated, 11 s, against an assumed minimum of 10 s. Over 20 seeded runs the mass estimate came within 5% in a mean of 1.56 s (standard deviation 0.68 s).
*Caution:* MATLAB/Simscape only, with experimental validation listed as future work. The 10 s requirement is an assumption of theirs. No number transfers to this project; the failure mechanism does.

**Canadian Space Agency.** [Canadarm, Canadarm2, and Canadarm3 comparative table](https://asc-csa.gc.ca/eng/iss/canadarm2/canadarm-canadarm2-comparative-table.asp). Headline figures for the arm.

**Freer, Guo, Deligianni, and Yang (2020).** "On-Orbit Operations Simulator for Workload Measurement during Telerobotic Training." [arXiv 2002.10594](https://arxiv.org/pdf/2002.10594).
A Unity training simulator used to study operator workload. No contact physics; a grapple means coming within 1 m. Gives ground-control communication latency of 0.3 to 0.5 s each way, and tests round-trip delays of 0, 0.5, 1.0, and 1.5 s between an operator's command and seeing the result.
*Caution:* that is a human teleoperation delay. It is not the delay of a sensor feeding an automatic controller, which is what this project's model has.

**NASA, SSP 50235 (baseline, 10 February 2000).** "Interface Definition Document (IDD) for International Space Station (ISS) Visiting Vehicles (VVs)." [Copy hosted by the University of Maryland](https://spacecraft.ssl.umd.edu/design_lib/SSP50235.ISSvehicleIDD.pdf).
The station programme's requirements on any visiting vehicle. Read for the paragraphs on capture by the arm (4.2.2.1.2, 4.6.2, 4.6.8.5, 5.1.7.3) only; the rest was searched, not read. It has no capture rates and no fixture dimensions. It points to where they are: see "Known but not read".
*Caution:* a 2000 baseline, written before HTV, Dragon, or Cygnus flew. Later revisions may differ. The berthing-box document it cites is numbered "JSC TBD".

### Read through a summary

**US patent 4,750,769 (Tebb, Spar Aerospace, 1988), "Auxiliary grapple fixture", and US patent 4,929,011 (Vandersluis and Quittner, 1990), "Grapple fixture".** Read through a summarising fetch for geometry. Neither gives a dimension. The first says the standard fixture weighs about 27 lb and that protrusions on its three cam arms mate with matching ones in the end effector. The second describes a different, cone-shaped fixture, not the one on Cygnus.

**International External Robotic Interface Interoperability Standards, baseline (2019).** [PDF](https://internationaldeepspacestandards.com/wp-content/uploads/2024/02/robotic_baseline_final_3-2019.pdf). Text searched for grapple fixture and capture terms. It has a picture of the flight releasable grapple fixture and a discussion of release mechanisms, and says visiting vehicles' fixtures release as a whole assembly of more than 12 kg. No dimensions and no capture envelope.

**Zhang, Verhagen, Vega, McKeen, and Manchester (2026).** "mjorbit: A Simulation Framework for Space Robotics." [arXiv 2609.08010](https://arxiv.org/abs/2609.08010), submitted 7 September 2026.
Extends MuJoCo with orbit propagation, spacecraft actuators, and sensors, with CPU and GPU backends. Points checked:

- Its docking example closes the latch with "a conditional weld constraint between the port frames", switched on when separation is under 0.2 m and attitude error under 5°. Contact is modelled "at the latch level". The snare-and-pull-in mechanism studied here has no counterpart in it.
- An Astrobee robot with a parallel-jaw gripper grasps a handle, succeeding in 88% of 1,024 parallel simulations.
- In a two-body collision test, zero-gravity and orbit-coupled runs "are indistinguishable" through the impact and diverge after roughly 0.2 hours. That supports using zero gravity for an attempt lasting about a minute.
- The authors state that "the validation in this paper is sim-to-sim" and that hardware and on-orbit tests are still needed.

**Schwartz, Hansson, Bodmer, Sternberg, Jia-Richards, and Albee (2026).** "SmallSatSim: A High-Fidelity Simulation and Training Toolkit for Microgravity Robotic Close Proximity Operations." [arXiv 2603.14598](https://arxiv.org/html/2603.14598v1), 15 March 2026.
A MuJoCo toolkit for small free-flying satellites: control, learning on GPU, configurable failures, and contact. Points checked:

- It has a contact-rich docking example, reported as one trial (first contact at 16.9 s, peak force 2.06 N), not a sweep.
- The authors call their scenarios "illustrative examples, rather than exhaustive benchmarks".
- It involves thruster-driven free-flyers. There is no robot arm and no grapple fixture.
- It notes that MuJoCo Warp is a GPU implementation of MuJoCo built on NVIDIA Warp. This matters for any comparison with a second engine: rerunning in Newton with that solver would largely be comparing MuJoCo with itself.

**MuJoCo documentation, "Overview" and "Computation" chapters.** [mujoco.readthedocs.io](https://mujoco.readthedocs.io/en/stable/overview.html). Checked for how the engine treats collision shapes: convex shapes only, a non-convex mesh replaced by its convex hull, hollow objects as a union of convex pieces, contacts as points with a frame and a distance, and contact that allows some penetration.

**Wei, Liu, Ling, and Su (2022), project page.** "Approximate Convex Decomposition for 3D Meshes with Collision-Aware Concavity and Tree Search." ACM Transactions on Graphics 41(4). [colin97.github.io/CoACD](https://colin97.github.io/CoACD/). The authors' summary and examples, not the paper. States the problem (earlier splitting methods lose functional details such as openings), the three changes they make, and the drawer-handle comparison with V-HACD. The page gives no success-rate numbers.

### Reported, on collision geometry

From a Perplexity conversation on 2026-10-11. The MuJoCo and CoACD points above were checked; these were not.

| Claim | Attributed to | Status |
|---|---|---|
| GJK finds the distance between two convex shapes by asking each for its farthest point in a direction, without building their Minkowski difference | Gilbert, Johnson, and Keerthi (1988), via Wikipedia | Reported |
| V-HACD splits a shape using a voxel grid; finer settings keep more detail and take longer | V-HACD's documentation | Reported |
| Unity does not allow a concave mesh collider on a body that moves under physics, and recommends compound colliders | Unity manual | Reported. Engine-specific |
| PhysX supports signed-distance-field collision for moving non-convex objects | NVIDIA Omniverse documentation | Reported |
| Rule of thumb: simple or compound shapes for moving objects, detailed meshes for stationary surroundings | Unity and PhysX documentation | Reported |

### Known but not read

| Source | Why it matters | Status |
|---|---|---|
| Lucier and Smith (2010), "Cosmic Catch: Canadarm2's First Capture of a Free-Flying Vehicle", IAC-10.B6.1.3 | Operational risks and limits of the first capture. Likely has free-drift rates and timing | Full paper restricted. A library login may work |
| Uyama et al. (2009), contact dynamics between the LEE and a floating target, JAXA workshop | Earlier work by the Honda group | Abstract only |
| CSA, *MSS Reference Guide*, v3.4 (2015) | Cited by Chang and Marquez. Likely has joint rates and modes | Not found online |
| NASA, *HTV Capture Procedure* (2014) | Cited by Chang and Marquez. The actual steps and limits | Not found online |
| *ISS Robotics Group Robotics Book*, JSC-48540 (2001) | Cited by Chang and Marquez | Not found online |
| "Canada and the International Space Station Program", SpaceOps 2025, paper 0266 | Reported to cover the history of free-flyer capture, including the 50th on 6 August 2024 | Reported, not read |
| Snare cable dynamics paper, *J. Central South University* (2013) | Flexible cable model of a snare end effector | Paywalled |
| NSTS 07700, Volume XIV, Appendix 8, "Payload Deployment and Retrieval System" | The Shuttle programme's definition of the standard grapple fixture and the end effector's capture envelope. Named by SSP 50235 as the requirement for a flight releasable grapple fixture | Not found online. SSP 50235 prints the volume as "XIX"; other sources say XIV |
| NSTS 21000-IDD-ISS, section 14 | Named by SSP 50235 alongside it | Not found online |
| SSP 42004, "Mobile Servicing System to User Interface Control Document (Generic)", and SSP 41167, the MSS segment specification | Canadarm2's own interface and payload-handling requirements. The likeliest home of the LEE's capture envelope and allowed rates | Not found online |
| Gilbert, Johnson, and Keerthi (1988), "A Fast Procedure for Computing the Distance Between Complex Objects in Three-Dimensional Space" | The distance algorithm behind most convex collision detection | Not read |
| Mamou, V-HACD | The widely used tool for splitting a mesh into convex pieces | Documentation reported, not read |
| Todorov, Erez, and Tassa (2012), "MuJoCo: A Physics Engine for Model-Based Control" | The engine's own paper: its contact formulation and why | Abstract reported, not read |
| US patent 4929009A, "End effector" | Design description of the snare and latch mechanism | Reported, not read |
| "Canadarm: The SRMS Technical Details", IEEE | Shuttle arm figures | Reported, not read. Gives a rigidize load in "kg", which is not a force unit |

### Reported, on ground testing and earlier work

From a Perplexity summary. None was opened successfully (the first sits behind a browser check).

| Source | What it is reported to show | Why it matters here |
|---|---|---|
| Li et al. (2021), "Estimation of Vibration Characteristics of a Space Manipulator From Air Bearing Supported Test Data", *Frontiers in Robotics and AI*, DOI 10.3389/frobt.2021.641165 | A small lab manipulator's vibration frequency measured at 0.3750 Hz unsupported and 0.2222 Hz on air bearings; a correction brought the prediction to 0.3390 Hz, cutting the error from 40.75% to 9.6%. Identified damping stayed too high | Ground tests change the dynamics they are meant to validate. A simulation that matches hardware is not thereby validated for orbit |
| "Experimental Validation of Docking and Capture Using Space Robotics Technology", NASA report indexed 1993, [NTRS 19930013118](https://ntrs.nasa.gov/api/citations/19930013118/downloads/19930013118.pdf) | Planar air-bearing experiments on docking with misalignment, contact stabilisation, impedance control, teleoperation delay, parameter identification, flexible payloads | These concerns have been studied for decades. No claim to have discovered them |
| ESA-hosted presentation on a planar air-bearing microgravity simulator | Limits of such testbeds: motion in one plane, finite area, scaled-down hardware, careful calibration | A 3D simulation can reach combinations a planar rig cannot, at the price of assumed contact models |
| "The analysis of capture strategy for redundant space manipulator...", *Advances in Mechanical Engineering* | Reported to discuss attitude regulation of a snare-type end effector with a contact model | A lead on snare capture strategy. Full text not retrieved |

## 4. Numbers

### The arm

| Quantity | Value | Source | What it is | Label |
|---|---|---|---|---|
| Length | 17 m | CSA | Published figure | Read |
| Length | 17.6 m | Honda et al., Table 2 | "Max length" in a modelling paper | Disputed (minor) |
| Mass | 1,497 kg | CSA | Published figure | Read |
| Mass | 1.8 t | Honda et al., Table 2 | Rounded value in a modelling paper | Disputed |
| Handling capacity | 116 t | Honda et al., Table 2 | Published figure | Read |
| Boom diameter | 35 cm | CSA | Published figure | Read |
| Joints | 7: three at each end, one elbow; ±270° each | CSA | Published figure | Read |
| Tip speed, unloaded | 37 cm/s | CSA | Published figure | Read |
| Tip speed, loaded | 2 cm/s under ground control; 15 cm/s supporting spacewalks | CSA | Published figure | Read |
| Rates near structure | "Vernier rates if within 1.5 m of structure" | Chang and Marquez | Procedure step. No numerical rate given | Read |
| Per-joint rate limits | 1.7°/s | none | This model's choice | Assumed |
| Link masses and inertias | split of about 1,400 kg | none | This model's choice | Assumed |
| Arm flexibility | none | none | The model's arm is rigid. Honda et al. suspect unmodelled flexibility at the arm's base explains vibration their model underpredicts | Assumed |

### The end effector (LEE)

| Quantity | Value | Source | What it is | Label |
|---|---|---|---|---|
| Free-flyer capture time | 30 s for snare, rigidize, and latch together | Walker and Vandersluis | Design requirement | Read |
| Snare closing | ring turns to about 75°, within 3 s maximum | Walker and Vandersluis | Test description | Read |
| Rigidize preload | 4,893 N (1,100 lb) | Walker and Vandersluis | Design value | Read |
| Latch load | 16,013 to 17,125 N at each of 4 latches; 64,054 N total | Walker and Vandersluis | Design value | Read |
| Latch time | 6 s at normal speed | Walker and Vandersluis | Test description | Read |
| Worst-case capture tested | 4 in radial offset, 15° pitch/yaw, with 156 N side load | Walker and Vandersluis | Test condition. The side load is "derived from the theoretical force to back drive the closest arm joint" | Read |
| Worst-case rigidize tested | 15° pitch/yaw, 10° roll, plus axial offset, with 448 N axial load | Walker and Vandersluis | Test condition. The load simulates "an average arm back driving while rigidizing" | Read |

From the Shuttle arm's end effector (Daniell and Sachdev), for comparison:

| Quantity | Value | What it is | Label |
|---|---|---|---|
| Size and mass | 0.34 m diameter, 0.46 m long, 29.5 kg | Design constraint | Read |
| Misalignment tolerance | ±0.1 m lateral, 0.1 m axial, up to 15° | Requirement and capture envelope figure | Read |
| Capture and rigidize times | under 3 s and under 20 s | Requirement | Read |
| Relative velocity at capture | up to 0.031 m/s | Requirement | Read |
| Impact design velocity | 0.122 m/s | Structural design case, not a capture requirement | Read |
| Rigidize load | about 3,560 N in the grapple shaft | Design value | Read |
| No interface separation up to | 474.5 N m bending | Requirement | Read |
| Up to 3° separation allowed at | 1,627 N m bending | Requirement | Read |
| Roll moment carried | 949 N m | Requirement | Read |
| Snare ring rotation | 80° | Design description | Read |

### Snare contact

| Quantity | Value | Source | What it is | Label |
|---|---|---|---|---|
| Static friction, shaft to snare wire | 0.3 | Honda et al., Table 3 | Chosen simulation input | Read |
| Dynamic friction | 0.1 | Honda et al., Table 3 | Chosen simulation input | Read |
| Stiction transition velocity | 1.0 × 10⁻² m/s | Honda et al., Table 3 | Friction model setting, not a drift speed | Read |
| Friction transition velocity | 1.0 m/s | Honda et al., Table 3 | Friction model setting | Read |
| Snare wire stiffness | 5.55 × 10⁵ N/m | Honda et al., Table 4 | Starting value for fitting, not the fitted result | Read |
| Grapple fixture base stiffness | 1.00 × 10⁸ N/rad as printed | Honda et al., Table 4 | Starting value. The unit looks wrong for a rotational stiffness | Read |
| Snare wire model angular rate | 29°/s | Honda et al., Table 4 | Starting value for the rotating-rod model. Not an arm joint rate | Read |
| Friction in this model | 0.6 | none | This model's choice | Assumed |

Honda et al. report that the fixture base stiffness "has much larger effect on the early phase of capture", especially on the frequency of roll vibration, and treat it as the key parameter.

### The vehicle and the approach

| Quantity | Value | Source | What it is | Label |
|---|---|---|---|---|
| Cygnus (Enhanced) | 3.07 m diameter, 6.39 m long, up to 8,050 kg loaded | Public data | Published figure | Read |
| Cygnus (Enhanced), empty | 1,800 kg dry | Wikipedia's infobox, which cites no source for it | Published figure, unsourced | Reported |
| Cygnus (Enhanced), cargo | 3,500 kg capacity; 3,785 kg and 3,857 kg carried on NG-20 and NG-21 (8,345 and 8,503 lb) | Wikipedia | Capacity, and two missions' loads | Reported |
| Cygnus (Enhanced), propellant | 1,218 kg | Wikipedia, body text, no source cited | Capacity at launch. How much is left at capture is not found | Reported |
| Cygnus mass at capture | roughly 5,000 to 7,000 kg | Sum of the three rows above: empty, plus 2,500 to 3,900 kg of cargo, plus whatever propellant is left | An estimate, not a published figure | Assumed |
| HTV | 16 t, 9.8 m long, 4.4 m diameter | Honda et al., Table 1 | Published figure | Read |
| Capture point | about 10 m from the station; 12 m for Cygnus XL | NASA and JAXA reports | Vehicle-to-station distance. Not the arm's standoff from the fixture | Read |
| Time to capture | 2 to 3 minutes once the crew has "Go" and the arm is in the capture window | Chang and Marquez | Typical duration. Not an abort limit | Read |
| Arm's starting distance from the fixture | 2 m | none | This model's choice | Assumed |
| Leftover drift and tumble in free drift | up to 0.031 m/s; up to 0.5°/s | Drift from the Shuttle requirement; tumble from nothing | This model's choice | Assumed |
| Time limit for free drift | 90 s | SSP 50235 (2000 baseline), 4.6.8.5 | Requirement on the vehicle: stay inside its berthing box "for up to 90 sec of free drift". Not a limit on how long the arm may take | Read |
| Holding position before capture | at least 5 minutes | SSP 50235 (2000 baseline), 4.2.2.1.2 | Requirement on the vehicle: keep its grapple fixture inside a defined grapple box | Read |
| Size of the grapple box | not given | SSP 50235 defers to a document numbered "JSC TBD" | | Open |

### Operations and sensing

| Quantity | Value | Source | Label |
|---|---|---|---|
| Who flies | Two crew: M1 on the hand controllers, M2 on procedures, cameras, and communication | Chang and Marquez | Read |
| Where | Robotics workstation in the Cupola; a second one is in the US Lab | Chang and Marquez | Read |
| Workstation | Three video monitors, two 3-axis hand controllers | Chang and Marquez | Read |
| Arm mode | Manual, with the LEE set to automatic capture | Chang and Marquez | Read |
| What is automatic | Snares close, carriage retracts, and for some vehicles latches and umbilical deploy | Chang and Marquez | Read |
| Operator's aim | To minimise arm oscillation with smooth inputs while capturing within the time limit | Chang and Marquez | Read |
| Arm cameras | Four: one each side of the elbow, one on each end | CSA | Read |
| How relative pose is seen | From the camera image of the target on the grapple fixture | Honda et al. | Read |
| Ground-control communication latency | 0.3 to 0.5 s each way | Freer et al. | Read. A teleoperation figure; see the caution in section 3 |
| Delay of an onboard pose sensor | unknown | none | Open |

## 5. Where sources disagree

- **Arm mass.** 1,497 kg (CSA) against 1.8 t (Honda et al., and reportedly eoPortal). Unexplained. Possibly the larger figure includes the end effectors or other equipment. This model follows CSA.
- **Arm length.** 17 m (CSA) against 17.6 m (Honda et al.). This model's geometry comes from the CSA 3D model.
- **Date of the first HTV capture.** July 2009 in Honda et al.; 17 September 2009 according to the Canadian Space Agency. Use the agency's date.
- **Shuttle end effector against LEE.** Rigidize load 3,560 N against 4,893 N. These are two devices, not a disagreement, but they are easy to mix up.

## 6. Still unknown

In order of how much they affect where capture fails in the model:

1. **Per-joint rate limits.** Not found in any source read. The model's 1.7°/s is invented.
2. **Leftover motion in free drift.** Honda et al. started their simulation from HTV telemetry but did not print the values. Angular rates appear only in their plots.
3. **The arm's starting distance from the fixture.** Not found.
4. **Free-drift time limit.** A 2000 requirement has the vehicle stay in its box for up to 90 s of free drift. How long the operator is allowed is still not found.
5. **Grapple fixture dimensions.** Shaft length and diameter, the cam at its tip, the three large cams, the base plate. No dimensioned drawing found after a second search (2026-10-11). The defining documents are named in section 3 and are not online. This now matters more: in the model, the plate's radius, the rim's radius, and the pin's length set the tilt at which the plate meets the rim (5 to 12°), and that contact is what removes tilt.
6. **Which fixture the arm stands on for a Cygnus capture.** Not found. The berthing port (Unity, Earth-facing) is not the same thing as where the arm is based.
7. **Link masses, joint torque limits, arm stiffness.** Not found.

The four unread documents at the top of the table in section 3 are the most likely places to find items 1 to 4.

## 7. What this project can and cannot claim

- **It is a case study, not a solution to a problem.** Canadarm2 captures cargo vehicles routinely; the 50th free-flyer capture is reported for 6 August 2024. A failure in this model is a failure of this model.
- **"No public answer could be found" is not "the field has no answer."** The real limits may be fully set out in requirements, tests, and procedures that are not public.
- **A capture demonstration in MuJoCo is not new.** Open tools for contact-rich space robotics exist (SmallSatSim and mjorbit, both 2026), and professional work models the snare as flexible cables. No gap in the literature is claimed.
- **The mechanism is a substitute, not a cheaper copy.** Rigid bars, a flat-backed knob, and a plate on a ring of spheres have different contact surfaces from cables, a cammed shaft, and cam arms. Results belong to the substitute.
- **The controller is part of every result.** Its rate cap, tolerances, and estimator are invented. "Capture fails above this rate" always means "this controller and mechanism fail above this rate".
- **Two kinds of uncertainty.** Doubt about the encounter (drift, tumble, alignment, measurement error) is what a real controller would face. Doubt about the model (shapes, friction, invented limits) is doubt about whether the simulation represents the real system. Robustness to the first says nothing about the second.
- **A mechanism's design tolerance is not a limit on a visiting vehicle's motion.** The 0.031 m/s used here is a requirement on the Shuttle end effector.

## 8. How this was researched

Perplexity searches found most of the sources and several of the ideas; the sources were then opened and checked, and anything not checked is labelled Reported. Several of Perplexity's citation links pointed at the wrong work even where the claim was right, which is the reason for that label.

The searches, in order: the capture operation and its numbers; a critique of the plan against recent MuJoCo space-robotics work; why capture fails and what ground tests can show; fixture geometry and allowed rates (nothing dimensional found); collision geometry; and the vehicle's mass.
