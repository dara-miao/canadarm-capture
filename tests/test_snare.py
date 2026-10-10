"""Milestone 2 checks: the snare centres, seats, and holds a pin that starts inside the cavity.

The arm holds still and the vehicle starts at rest; approaching is milestone 3.
"""

import mujoco
import numpy as np
import pytest

from capture import scene, snare

INSERTED = -0.28  # pin tip 0.28 m inside the cavity, past the snare plane
SEATED = -0.30  # pin length: the fixture plate rests on the rim
PULL_TIME = 20.0


@pytest.fixture(scope="module")
def model():
    return scene.build_model()


def run(model, lateral=(0.0, 0.0), grapple=True, pull=0.0, stop_after=None):
    """Run the grapple sequence, then pull the pin straight out with `pull` newtons."""
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=INSERTED, lateral=lateral)
    vid = model.body("vehicle").id
    dt = model.opt.timestep
    total = stop_after if stop_after is not None else snare.SEQUENCE_TIME + 2.0 + PULL_TIME
    for i in range(int(round(total / dt))):
        t = i * dt
        if grapple:
            scene.set_snare(model, data, *snare.grapple_command(t))
        data.qfrc_applied[:] = 0
        if pull and t > snare.SEQUENCE_TIME + 2.0:
            # Pull along the pin, through the pin. A force through the vehicle's centre
            # of mass would also lever the fixture sideways; that is a separate question.
            out = data.site("lee_mouth").xmat.reshape(3, 3)[:, 2]
            mujoco.mj_applyFT(model, data, pull * out, np.zeros(3), data.site("pin_tip").xpos, vid, data.qfrc_applied)
        mujoco.mj_step(model, data)
    return data


def test_open_snare_does_not_touch_the_pin(model):
    data = run(model, lateral=(0.05, 0.0), grapple=False, stop_after=1.0)
    assert data.ncon == 0


def test_snare_centres_an_offset_pin(model):
    data = run(model, lateral=(0.06, 0.02), stop_after=snare.CLOSE_TIME + snare.SETTLE_TIME)
    assert np.linalg.norm(scene.pin_offset(model, data)[:2]) < 0.005


def test_pull_in_seats_the_fixture_plate(model):
    data = run(model, stop_after=snare.SEQUENCE_TIME + 2.0)
    assert scene.pin_offset(model, data)[2] == pytest.approx(SEATED, abs=0.002)


@pytest.mark.parametrize("lateral", [(0.0, 0.0), (0.06, 0.02), (0.085, 0.0)])
def test_capture_holds_against_500_newtons(model, lateral):
    offset = scene.pin_offset(model, run(model, lateral=lateral, pull=500.0))
    assert offset[2] == pytest.approx(SEATED, abs=0.002)
    assert np.linalg.norm(offset[:2]) < 0.005


def test_overload_backs_the_pin_out_but_keeps_it(model):
    # 7000 N is about twice the pull-in force limit: the plate unseats, the snare still holds.
    z = scene.pin_offset(model, run(model, pull=7000.0))[2]
    assert SEATED + 0.02 < z < 0


def test_seated_capture_resists_the_specified_bending_moment(model):
    """The Shuttle arm's end effector was required to show no interface separation up to
    474.5 N m of cross-axis bending (Daniell and Sachdev, 1982)."""
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=INSERTED)
    vid = model.body("vehicle").id
    dt = model.opt.timestep
    hold = snare.SEQUENCE_TIME + 2.0
    for i in range(int(round((hold + PULL_TIME) / dt))):
        t = i * dt
        scene.set_snare(model, data, *snare.grapple_command(t))
        data.qfrc_applied[:] = 0
        if t > hold:
            across = data.site("lee_mouth").xmat.reshape(3, 3)[:, 0]
            mujoco.mj_applyFT(model, data, np.zeros(3), 474.5 * across, data.site("pin_tip").xpos, vid, data.qfrc_applied)
        mujoco.mj_step(model, data)
    assert scene.pin_axis_error(model, data) < np.radians(0.5)
    assert scene.pin_offset(model, data)[2] == pytest.approx(SEATED, abs=0.002)


def test_without_the_snare_the_vehicle_escapes(model):
    z = scene.pin_offset(model, run(model, grapple=False, pull=100.0))[2]
    assert z > 1.0
