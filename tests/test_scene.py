"""Milestone 1 checks: the scene is physically sane before any capture logic exists."""

import mujoco
import numpy as np
import pytest

from capture import scene


@pytest.fixture(scope="module")
def model():
    return scene.build_model()


def steps(model, seconds):
    return int(round(seconds / model.opt.timestep))


def test_zero_gravity_and_layout(model):
    assert np.all(model.opt.gravity == 0)
    # 7 arm motors, plus the snare drive and the carriage drive
    assert model.nu == len(scene.ARM_JOINTS) + 2 == 9
    # 7 arm joints, 4 snare slides, one free joint (3 position + 4 quaternion)
    assert model.nq == 7 + 4 + 7


def test_arm_geometry_matches_the_csa_model(model):
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)  # all joints zero: arm folded
    anchor = {j: data.joint(j).xanchor for j in scene.ARM_JOINTS}
    axis = {j: data.joint(j).xaxis for j in scene.ARM_JOINTS}
    # the two booms are the same length, shoulder pitch to elbow and elbow to wrist pitch
    def boom(a, b):
        along = anchor[a] - anchor[b]
        return np.linalg.norm(along - (along @ axis[b]) * axis[b])
    assert boom("shoulder_pitch", "elbow_pitch") == pytest.approx(7.04, abs=0.01)
    assert boom("wrist_pitch", "elbow_pitch") == pytest.approx(7.04, abs=0.01)
    # the three pitch axes are parallel; each roll and yaw axis is perpendicular to its neighbour
    assert abs(axis["shoulder_pitch"] @ axis["elbow_pitch"]) == pytest.approx(1.0)
    assert abs(axis["wrist_pitch"] @ axis["elbow_pitch"]) == pytest.approx(1.0)
    assert axis["shoulder_yaw"] @ axis["shoulder_pitch"] == pytest.approx(0.0, abs=1e-9)
    assert axis["wrist_yaw"] @ axis["wrist_roll"] == pytest.approx(0.0, abs=1e-9)
    # the base end effector's tip sits on the station, at the world origin
    assert model.body("arm_root").pos + np.array([3.81, -0.04, -1.23]) == pytest.approx(0.0, abs=1e-9)


def test_ready_pose_points_away_from_the_station(model):
    data = mujoco.MjData(model)
    scene.reset(model, data)
    mouth = data.site("lee_mouth")
    assert mouth.xpos == pytest.approx(scene.READY_MOUTH, abs=1e-4)
    assert mouth.xmat.reshape(3, 3)[:, 2] == pytest.approx([0, 0, 1], abs=1e-4)


def test_pin_is_aligned_with_cavity(model):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=0.5, lateral=(0.03, -0.02))
    mouth = data.site("lee_mouth")
    R_l = mouth.xmat.reshape(3, 3)
    offset = R_l.T @ (data.site("pin_tip").xpos - mouth.xpos)
    assert offset == pytest.approx([0.03, -0.02, 0.5], abs=1e-9)
    # pin axis (vehicle +x) points into the cavity
    pin_axis = data.body("vehicle").xmat.reshape(3, 3)[:, 0]
    assert pin_axis == pytest.approx(-R_l[:, 2], abs=1e-9)
    assert data.ncon == 0


def test_free_vehicle_conserves_momentum(model):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=3.0)
    vid = model.body("vehicle").id
    dof = model.joint("vehicle_free").dofadr[0]
    data.qvel[dof : dof + 3] = [0.01, 0.02, 0.005]  # drifting away, m/s
    data.qvel[dof + 3 : dof + 6] = [0.01, 0.02, 0.005]  # tumbling, rad/s

    def momenta():
        mujoco.mj_forward(model, data)
        mujoco.mj_subtreeVel(model, data)
        return data.subtree_linvel[vid].copy(), data.subtree_angmom[vid].copy()

    v0, L0 = momenta()
    for _ in range(steps(model, 120.0)):
        mujoco.mj_step(model, data)
    v1, L1 = momenta()

    assert data.ncon == 0
    # the body origin sits about 2 m from the centre of mass, which costs
    # the integrator a little accuracy on a tumbling body
    assert np.linalg.norm(v1 - v0) / np.linalg.norm(v0) < 1e-4
    assert np.linalg.norm(L1 - L0) / np.linalg.norm(L0) < 1e-3


def test_arm_holds_ready_pose(model):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=3.0)
    adr = scene.arm_qpos_adr(model)
    for _ in range(steps(model, 10.0)):
        mujoco.mj_step(model, data)
    assert data.qpos[adr] == pytest.approx(scene.READY_POSE, abs=1e-6)


def test_arm_tracks_a_step_command(model):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=3.0)
    adr = scene.arm_qpos_adr(model)
    target = scene.READY_POSE + np.array([0.1, 0.05, -0.1, 0.1, 0.05, 0.1, -0.1])
    data.ctrl[: len(scene.ARM_JOINTS)] = target
    for _ in range(steps(model, 30.0)):
        mujoco.mj_step(model, data)
    assert data.qpos[adr] == pytest.approx(target, abs=5e-3)
    dof = [model.joint(n).dofadr[0] for n in scene.ARM_JOINTS]
    assert np.abs(data.qvel[dof]).max() < 1e-3


@pytest.mark.skipif(not scene.meshes_available(), reason="3D models not fetched")
def test_meshes_do_not_change_the_physics():
    plain, meshed = scene.build_model(meshes=False), scene.build_model(meshes=True)
    assert meshed.nmesh > 0 and plain.nmesh == 0
    assert meshed.body_mass == pytest.approx(plain.body_mass)
    assert meshed.body_inertia == pytest.approx(plain.body_inertia)
    assert meshed.body_ipos == pytest.approx(plain.body_ipos)
    collides = lambda m: int(((m.geom_contype != 0) | (m.geom_conaffinity != 0)).sum())
    assert collides(meshed) == collides(plain)


def test_roll_turns_the_hull_about_the_pin_without_moving_the_pin(model):
    a, b = mujoco.MjData(model), mujoco.MjData(model)
    scene.reset(model, a, lateral=(0.03, 0.0))
    scene.reset(model, b, lateral=(0.03, 0.0), roll=np.radians(10.0))
    assert scene.pin_offset(model, b) == pytest.approx(scene.pin_offset(model, a), abs=1e-9)
    assert scene.pin_axis(b) == pytest.approx(scene.pin_axis(a), abs=1e-9)
    # the hull's centre swings about the pin axis, 0.41 m off it, by 10 degrees
    moved = np.linalg.norm(b.body("vehicle").xpos - a.body("vehicle").xpos)
    assert moved == pytest.approx(2 * np.hypot(0.41, 2.085) * np.sin(np.radians(5.0)), rel=0.01)


def test_friction_and_fixture_mount_are_build_options():
    default = scene.build_model(meshes=False)
    colliding = (default.geom_contype != 0) | (default.geom_conaffinity != 0)
    assert default.geom_friction[colliding, 0] == pytest.approx(0.3)
    assert default.joint("shoulder_pitch").frictionloss[0] == pytest.approx(200.0)

    slick = scene.build_model(meshes=False, friction=0.1)
    assert slick.geom_friction[colliding, 0] == pytest.approx(0.1)

    sprung = scene.build_model(meshes=False, fixture_stiffness=2.0e4)
    assert sprung.nq == default.nq + 4  # one ball joint
    assert sprung.joint("fixture_mount").stiffness[0] == pytest.approx(2.0e4)
    with pytest.raises(ValueError):
        scene.build_model(meshes=False, fixture_stiffness=1.0e8)  # too stiff for the timestep


def test_solver_settings_are_build_options():
    default = scene.build_model(meshes=False)
    assert (default.opt.solver, default.opt.cone, default.opt.iterations) == (
        mujoco.mjtSolver.mjSOL_NEWTON, mujoco.mjtCone.mjCONE_PYRAMIDAL, 100,
    )  # fmt: skip
    changed = scene.build_model(meshes=False, solver="PGS", cone="elliptic", iterations=50)
    assert (changed.opt.solver, changed.opt.cone, changed.opt.iterations) == (
        mujoco.mjtSolver.mjSOL_PGS, mujoco.mjtCone.mjCONE_ELLIPTIC, 50,
    )  # fmt: skip
    with pytest.raises(AttributeError):
        scene.build_model(meshes=False, solver="Jacobi")
