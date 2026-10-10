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

### Read through a summary

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
- It notes that MuJoCo Warp is a GPU implementation of MuJoCo built on NVIDIA Warp. This matters for experiment C: rerunning in Newton with that solver would largely be comparing MuJoCo with itself.

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

### Reported for background only

From a Perplexity summary, not opened: AmericaSpace's account of the Cygnus OA-6 capture (free drift with thrusters disabled); the Canadian Space Agency's "cosmic catches" page; NASA blog posts on the 13 April 2026 Cygnus XL capture (capture point about 12 m; capture and installation as separate events); Uyama et al. (2012, i-SAIRAS) on a compliant wrist and rebound; Abiko et al. (2006, IROS) and others on impedance control for free-floating robots; and a 2026 *Aerospace* paper on a different, two-finger capture mechanism. These shaped sections 1 and 2. None supplies a number used in the model.

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
| HTV | 16 t, 9.8 m long, 4.4 m diameter | Honda et al., Table 1 | Published figure | Read |
| Capture point | about 10 m from the station; 12 m for Cygnus XL | NASA and JAXA reports | Vehicle-to-station distance. Not the arm's standoff from the fixture | Read |
| Time to capture | 2 to 3 minutes once the crew has "Go" and the arm is in the capture window | Chang and Marquez | Typical duration. Not an abort limit | Read |
| Arm's starting distance from the fixture | 2 m | none | This model's choice | Assumed |
| Leftover drift and tumble in free drift | up to 0.031 m/s; up to 0.5°/s | Drift from the Shuttle requirement; tumble from nothing | This model's choice | Assumed |
| Time limit for free drift | none | none | Chang and Marquez mention a "required time limit" without a number | Open |

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
4. **Free-drift time limit.** Mentioned without a number.
5. **Grapple fixture dimensions.** Shaft length and diameter, the cam at its tip, the three large cams. No dimensioned drawing found.
6. **Which fixture the arm stands on for a Cygnus capture.** Not found. The berthing port (Unity, Earth-facing) is not the same thing as where the arm is based.
7. **Link masses, joint torque limits, arm stiffness.** Not found.

The four unread documents at the top of the table in section 3 are the most likely places to find items 1 to 4.

## 7. What this project can and cannot claim

This section came out of a critique of the plan (see the log). The points below were checked against the sources where they rest on one.

### This is a case study, not a solution to a problem

Canadarm2 already captures cargo vehicles. The Canadian Space Agency reports successful captures as routine, and the 50th free-flyer capture is reported for 6 August 2024. The operation does not need this simulation, and the agencies have their own simulators for training and preparation (NASA's on-board trainer and its track-and-capture scoring tool are reported, not read).

So the honest reason for the project is this: an established capture operation is a concrete case for learning contact-rich robotics and simulation. The project looks at how a simplified model produces successful and failed captures, and how sensitive those predictions are to its own physical and control assumptions.

Three things follow.

- **A failure in the model is not a weakness in Canadarm2.** When the model fails at four times the tested drift and tumble, that is a failure regime of this mechanism, this controller, and these assumptions.
- **"I cannot find a public answer" is not "the field has no answer."** The real limits may be fully characterised in requirements, tests, and procedures that are not public.
- **No gap needs declaring in advance.** If the experiments turn up something reproducible and useful, such as an outcome boundary that moves a lot under a seemingly minor approximation, that finding is the contribution. Until then the project stands as an engineering study with a transparent model, careful experiments, clear failure analysis, and stated limits.

### The gap is narrower than "nobody has done this"

Open MuJoCo tools for contact-rich space robotics now exist: SmallSatSim and mjorbit, both from 2026. A capture demonstration in MuJoCo is therefore not new. What the existing work leaves open is more specific:

| Work | What it does | What it leaves for this project |
|---|---|---|
| Honda et al. (2014) | Reconstructs one real capture and fits parameters to its telemetry | Sweeps across conditions to find where capture fails |
| Arbatani et al. (2023) | Simulates the flexible cables faithfully | Accessible experiments on a declared simplification, including how much the simplification matters |
| Freer et al. (2020) | Measures operator workload | Physical engagement, pull-in, and retention |
| SmallSatSim (2026) | General toolkit; one illustrative docking trial | A dedicated arm-and-fixture task with structured failure analysis |
| mjorbit (2026) | Orbit-coupled simulation; docking by a conditional weld | The mechanics of the capture interface itself |

These are differences of emphasis. They are not evidence that no one has run a similar experiment.

A statement of the gap that the sources support: existing work models capture dynamics, flexible snares, and contact control, and recent open tools simulate contact in microgravity. None of that by itself says how far a particular capture prediction can be trusted when the mechanism, actuators, sensing, and numerics are uncertain. This project looks at that question for one simplified arm-and-fixture scenario.

### Three envelopes

"Capture envelope" can mean the *geometric* envelope of the mechanism, the *closed-loop* envelope of a controller using that mechanism, or the *operational* envelope a flight procedure allows. A mechanism's design tolerance is not a limit on a visiting vehicle's drift. This project measures the second kind, for its own controller and mechanism. The plan's definitions section carries this.

One consequence: the 0.031 m/s used in tests comes from the Shuttle end effector's requirements. Earlier entries in the build log call the tested range "sourced capture limits". The accurate phrase is "a range derived from the Shuttle end-effector paper".

### Engaged, seated, retained

Catching the pin, finishing pull-in, and surviving a later disturbance are three different achievements. The model's "captured" label currently means seated. Since the seated joint lets go above about 850 N m, a retention check belongs in the definition of success.

### The mechanism is a substitute, not a cheaper copy

Three rigid bars and a flat-backed knob have different contact surfaces and kinematics from three cables and a cammed shaft. The knob's shape was chosen partly because a ball tip failed. Any envelope measured here belongs to that substitute. The useful question is which findings survive plausible changes to it.

### The controller is part of the result

The rate cap, tolerances, and estimator gain are invented, and the tracking logic was changed because the first version let the pin escape. So a statement like "capture fails above this tumble rate" must read "this controller and mechanism fail above this rate under these conditions".

### Two kinds of uncertainty

The project deals with two different uncertainties, and showing robustness to one says nothing about the other.

| Kind | Examples | Who would face it | Which experiment |
|---|---|---|---|
| About the encounter | Leftover drift and tumble, starting alignment, measurement error, the vehicle's mass | A real controller, during a real capture | A |
| About the model | Rigid bars for cables, invented rate limits and gains, approximate fixture geometry, friction and contact softness, missing cams and flexibility | Nobody in flight. It is doubt about whether the simulation represents the real system | B and C |

A controller that copes with noisy measurements *inside the model* has not shown that the model is relevant. The strongest version of this project keeps the two apart and reports both.

### There is no single tolerance

The outcome depends on where contact begins, how fast relative motion spoils the alignment, whether the arm keeps tracking, whether the snare shuts before the pin escapes, whether pull-in completes, and whether the joint survives load. So "the error the arm can tolerate" is not one number. The question to ask is which combinations of conditions lead to each outcome, for a stated mechanism, controller, and numerical model, and how stable that classification is when those are changed.

### Why simulate at all

Ground experiments supply real material and mechanism behaviour, but planar testbeds restrict the motion and their supports alter inertia and damping (reported; see section 3). Simulation reaches conditions hardware cannot, but rests on assumed contact models. Neither is simply more accurate. The value is in stating the trade plainly.

### Claims and their standing

| Statement | Standing |
|---|---|
| Unknown inertial properties can change whether contact lasts long enough to attach | Shown in simulation for a different mechanism (read) |
| Ground-test supports can alter measured vibration and damping | Shown experimentally for a lab manipulator (reported) |
| Planar tests cannot reproduce every 3D misalignment | Stated in a presentation (reported) |
| Capture, impedance control, delay, and misalignment have long been studied experimentally | Supported by a 1993 NASA report (reported) |
| No public failure-boundary benchmark exists for a Canadarm2-like capture | Not established. Do not claim it |
| This project's combination of outcome labels, sweeps, and engine comparison is new | Not established. Describe it as the intended contribution |

### What the first batches do and do not show

They show the harness reaches both successful and unsuccessful regimes, and that a harsh condition exposes several failure paths. They do not show that sensing has no effect, which parameter causes the drop, or whether the boundary is smooth. Drift and tumble were scaled together, so their effects are confounded. Separate sweeps and matched trials are needed.

A perfect-knowledge baseline that always succeeds is still a result: it establishes the baseline inside the sampled range. Degraded sensing should be added to answer a question, not to produce failures.

## 8. What this means for the model

Applied on 2026-10-10 unless marked otherwise. The build log has the details and the test results.

| Finding | Before | Now |
|---|---|---|
| LEE rigidize preload is 4,893 N | 3,560 N, the Shuttle value | 4,893 N |
| Four latches add 64,054 N after rigidizing | No latches. The seated joint let go above about 850 N m | Latch stage added: 64,054 N as four forces at the rim, engaging only on a seated fixture |
| Whole sequence must fit in 30 s; snare within 3 s; latch about 6 s | Snare 2 s, pause 2 s, pull-in 10 s | Latch 6 s added. 20 s in total |
| Tested worst case: 4 in offset, 15° pitch/yaw, 10° roll | No roll | Roll about the pin axis added to scenarios, up to 10° |
| Arm back-drive resistance: 156 N side load, 448 N axial average | Limp arm had no resistance | 200 N m of joint friction, from 156 N at 1.3 m |
| Published friction input is 0.3 static, 0.1 dynamic | 0.6 | 0.3, with a build option for sensitivity runs. MuJoCo has one coefficient, so the dynamic value is not represented |
| Honda et al. model the wires as rigid rotating rods | Rigid sliding bars | No change. Noted as precedent |
| Fixture base stiffness strongly affects early capture | Fixture rigid on the hull | Optional sprung mount. Limited to 5e4 N m/rad by the timestep, so their 1e8 starting value cannot be reproduced |
| A person flies the arm, in Manual mode | Automatic controller | No change. Stated in the plan and README |
| Capture takes 2 to 3 minutes | 41 s to the snare firing | No change. Noted |
| Honda et al. fix shoulder roll when solving the arm's pose | All seven joints move | Optional, off by default |
| Success should include retention | "Captured" meant seated and at rest | "Captured" needs seated, latched, and retained under 1,627 N m for 5 s with under 3° of tilt. The load is borrowed from the Shuttle end effector |
| Engagement is a distinct stage | Not recorded | Recorded per attempt |
| Capture is a race between closing and escaping | Timing not recorded | Recorded: how long after firing the pin stayed catchable, up to the snare's 2 s closing time |
| Drift and tumble were varied together | One "wide" batch scaled both | `matched_sweep` varies one quantity with everything else, including the random seed, held fixed. To be used in experiment A |
| "Compliance" has several meanings | Unspecified | Named in the plan |
| Teleoperation latency is not sensor delay | Delay range cited to Freer et al. | Relabelled exploratory in the plan and code |
| Zero gravity holds for short horizons | Zero gravity throughout | No change. Timescale assumption stated in the plan |

## 9. Research log

**2026-10-10, session 1 (Claude).** Read the user's notes on NVIDIA's simulation stack and physics simulation basics. Found the 1982 Shuttle end-effector paper, the 2023 cable-simulation abstract, and the CSA comparison table. Could not open the 2010 "Cosmic Catch" paper or the JAXA 2009 abstract's full text.

**2026-10-10, session 2 (Dara, via Perplexity).** Three searches: the physics of free-flyer capture and its link to contact-rich manipulation; a hunt for the missing numbers; and newer work from 2018 to 2026. Found Honda et al. (2014) and Chang and Marquez (2018), and the lead to Walker and Vandersluis (1995). Established that the three highest-priority numbers are not in the accessible literature.

**2026-10-10, session 2 (Claude).** Opened and read Honda et al., Chang and Marquez, and Walker and Vandersluis. Every number Perplexity reported from the first two matched the source. Walker and Vandersluis had not been read by anyone yet and turned out to hold the Canadarm2-specific end-effector figures: 4,893 N rigidize preload, 64,054 N latch load, the 30 s capture requirement, and the worst-case test conditions with their back-drive loads.

**2026-10-10, session 3 (Dara, via Perplexity).** A critique of the plan and README, drawing on mjorbit, SmallSatSim, and Freer et al. Main points: the gap is narrower than "no MuJoCo capture simulator exists"; the plan mixed three kinds of envelope; the rigid-bar mechanism and the controller are both part of any result; "captured" needs a retention criterion; teleoperation latency is not sensor delay; compliance and the second-engine comparison were underspecified.

**2026-10-10, session 3 (Claude).** Checked the critique's claims about mjorbit and SmallSatSim against the papers through a summarising fetch; they held. Added section 7 and six rows to section 8, and revised the plan: reframed the question as a robustness study, added definitions and an explicit scope list, marked two decisions as superseded, split the values the model uses by where they come from, and tightened experiments A, B, and C.

*A caution about the Perplexity text itself.* Several of its citation links pointed at the wrong work: statements about SmallSatSim linked to the Honda paper, statements about Honda linked to an unrelated journal page, and statements about Freer linked to the cable-simulation abstract. The claims were right where checked, but the links cannot be relied on to find the source. This is the reason for the Reported label.

**2026-10-10, session 4 (Dara, via Perplexity).** Further reading on why capture fails and on what ground tests can and cannot show: Christidi-Loumpasefski et al. (2024) on contact time under mass uncertainty; Li et al. (2021) on air-bearing supports changing measured vibration; a 1993 NASA report and an ESA presentation on planar testbeds; a lead on snare capture strategy. Main ideas: capture is a race between engagement and separation; there are two kinds of uncertainty; there is no single tolerance number.

**2026-10-10, session 4 (Claude).** Downloaded and read the Christidi-Loumpasefski manuscript; the reported numbers matched. Could not open Li et al. (a browser check blocked it), so it stays Reported, as do the NASA report, the ESA presentation, and the snare-strategy lead. Added the "capture is a race" idea to section 2, four subsections to section 7, and one row to section 8.

**2026-10-10, session 5 (Dara, via Perplexity).** Dara objected that Canadarm2 already captures spacecraft, so the project cannot be motivated as solving that. Perplexity agreed and revised its assessment: the earlier framing overstated a mission need. The project is a case study for learning and for testing a model's assumptions. Whether it becomes research with a new finding is open.

**2026-10-10, session 5 (Claude).** Agreed and adopted. Added the first subsection of section 7 and revised the plan's "Why this project" and the README to match. The operational facts cited (routine captures, agency training simulators) are recorded as reported.
