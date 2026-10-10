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
