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


def test_arm_reach_matches_canadarm2(model):
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)  # all joints zero: arm straight
    reach = data.site("lee_mouth").xpos[2]
    assert reach == pytest.approx(17.6, abs=0.3)


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
    assert np.linalg.norm(v1 - v0) / np.linalg.norm(v0) < 1e-6
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
