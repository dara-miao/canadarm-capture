# Research notes

What we know about capturing a free-flying spacecraft with Canadarm2, where each fact comes from, and how far to trust it. This sits beside the [plan](PLAN.md) (what we intend to build) and the [build log](DEVLOG.md) (what we built and what happened).

The rule for this project: understand the real operation before running experiments or writing about them.

## How to read this

Every claim carries one of four labels.

| Label | Meaning |
|---|---|
| **Read** | Taken from the source itself, which was opened and read for this project |
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

**Canadian Space Agency.** [Canadarm, Canadarm2, and Canadarm3 comparative table](https://asc-csa.gc.ca/eng/iss/canadarm2/canadarm-canadarm2-comparative-table.asp). Headline figures for the arm.

**Freer, Guo, Deligianni, and Yang (2020).** "On-Orbit Operations Simulator for Workload Measurement during Telerobotic Training." [arXiv 2002.10594](https://arxiv.org/pdf/2002.10594).
A Unity training simulator used to study operator workload. No contact physics; a grapple means coming within 1 m. Useful only for its ground-control latency figure.

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
| Ground-control latency | 0.3 to 0.5 s each way | Freer et al. | Read |

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

## 7. What this means for the model

Nothing here has been applied yet. These are the changes the research points to.

| Finding | Current model | Suggested change |
|---|---|---|
| LEE rigidize preload is 4,893 N | 3,560 N, the Shuttle value | Use 4,893 N |
| Four latches add 64,054 N after rigidizing | No latches. The seated joint lets go above about 850 N m | Add a latch stage. This is what carries large bending loads in reality |
| Whole sequence must fit in 30 s; snare within 3 s; latch about 6 s | Snare 2 s, pause 2 s, pull-in 10 s | Keep the snare; fit pull-in and a latch stage inside 30 s |
| Tested worst case: 4 in offset, 15° pitch/yaw, 10° roll | Roll is uncontrolled and untested | Add roll misalignment to scenarios |
| Arm back-drive resistance: 156 N side load, 448 N axial average | Limp arm has zero servo torque | Give the limp arm a back-drive resistance of this size |
| Published friction input is 0.3 static, 0.1 dynamic | 0.6 | Use 0.3 as the baseline and treat friction as a sensitivity parameter |
| Honda et al. model the wires as rigid rotating rods | Rigid sliding bars | Supports the simplification. Worth saying so in the write-up |
| Fixture base stiffness strongly affects early capture | Fixture is rigid on the hull | Candidate parameter for experiment B |
| A person flies the arm, in Manual mode | Autonomous controller | State plainly that the model studies an automated capture |
| Capture takes 2 to 3 minutes | 41 s to the snare firing | Not wrong, but the model's approach is brisk. Note it |
| Honda et al. fix shoulder roll when solving the arm's pose | All seven joints move | Optional. Would make poses more comparable to theirs |

## 8. Research log

**2026-10-10, session 1 (Claude).** Read the user's notes on NVIDIA's simulation stack and physics simulation basics. Found the 1982 Shuttle end-effector paper, the 2023 cable-simulation abstract, and the CSA comparison table. Could not open the 2010 "Cosmic Catch" paper or the JAXA 2009 abstract's full text.

**2026-10-10, session 2 (Dara, via Perplexity).** Three searches: the physics of free-flyer capture and its link to contact-rich manipulation; a hunt for the missing numbers; and newer work from 2018 to 2026. Found Honda et al. (2014) and Chang and Marquez (2018), and the lead to Walker and Vandersluis (1995). Established that the three highest-priority numbers are not in the accessible literature.

**2026-10-10, session 2 (Claude).** Opened and read Honda et al., Chang and Marquez, and Walker and Vandersluis. Every number Perplexity reported from the first two matched the source. Walker and Vandersluis had not been read by anyone yet and turned out to hold the Canadarm2-specific end-effector figures: 4,893 N rigidize preload, 64,054 N latch load, the 30 s capture requirement, and the worst-case test conditions with their back-drive loads.
