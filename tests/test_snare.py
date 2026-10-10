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
    # 7,000 N is above the 4,893 N pull-in limit: the plate unseats to the carriage's end
    # stop, and the snare still holds.
    z = scene.pin_offset(model, run(model, pull=7000.0))[2]
    assert SEATED + 0.02 < z < 0


def test_the_snare_itself_gives_way_near_8000_newtons(model):
    # A limit of this model, not of the real mechanism: the load forces the bars apart.
    # What they give way against is not established; changing the drive's force limit
    # made no difference in the pilots. Real snare cables would not open this way.
    assert scene.pin_offset(model, run(model, pull=8000.0))[2] > 0


def test_grapple_sequence_fits_the_30_second_requirement():
    # Walker and Vandersluis (1995): 30 s for snare, rigidize, and latch together.
    assert snare.SEQUENCE_TIME <= 30.0
    assert snare.CLOSE_TIME <= 3.0
    assert snare.grapple_command(snare.PULL_IN_END) == (1.0, 1.0)
    assert snare.latch_command(snare.PULL_IN_END) == 0.0
    assert snare.latch_command(snare.SEQUENCE_TIME) == 1.0


def bend(model, moment, latch):
    """Seat the pin, optionally latch, then lever the vehicle sideways. Returns the pin's tilt and depth."""
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=INSERTED)
    vid = model.body("vehicle").id
    dt = model.opt.timestep
    load_from = snare.SEQUENCE_TIME + 2.0
    for i in range(int(round((load_from + PULL_TIME) / dt))):
        t = i * dt
        scene.set_snare(model, data, *snare.grapple_command(t))
        mujoco.mj_step1(model, data)
        data.qfrc_applied[:] = 0
        if latch:
            scene.apply_latch(model, data, snare.latch_command(t))
        if t > load_from:
            across = data.site("lee_mouth").xmat.reshape(3, 3)[:, 0]
            mujoco.mj_applyFT(model, data, np.zeros(3), moment * across, data.site("pin_tip").xpos, vid, data.qfrc_applied)
        mujoco.mj_step2(model, data)
    return scene.pin_axis_error(model, data), scene.pin_offset(model, data)[2]


def test_pull_in_alone_resists_the_no_separation_moment(model):
    """The Shuttle arm's end effector was required to show no interface separation up to
    474.5 N m of cross-axis bending (Daniell and Sachdev, 1982)."""
    tilt, depth = bend(model, 474.5, latch=False)
    assert tilt < np.radians(0.5)
    assert depth == pytest.approx(SEATED, abs=0.002)


def test_latches_carry_a_moment_that_pull_in_alone_cannot(model):
    # 1,627 N m is the Shuttle end effector's largest bending case. Pull-in alone gives
    # way at about its preload times the rim radius: 4,893 N x 0.24 m = 1,170 N m.
    unlatched_tilt, _ = bend(model, 1627.0, latch=False)
    latched_tilt, depth = bend(model, 1627.0, latch=True)
    assert unlatched_tilt > np.radians(3.0)
    assert latched_tilt < np.radians(0.5)
    assert depth == pytest.approx(SEATED, abs=0.002)
