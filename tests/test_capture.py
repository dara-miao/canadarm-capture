"""Milestone 3 checks: the arm approaches a moving vehicle and completes a capture."""

import mujoco
import numpy as np
import pytest

from capture import scene
from capture.controller import CaptureController, Phase
from capture.trial import run_trial


@pytest.fixture(scope="module")
def model():
    return scene.build_model()


def attempt(model, standoff=0.6, lateral=(0, 0), tilt_deg=(0, 0), drift=(0, 0, 0), tumble_deg=(0, 0, 0), **kw):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=standoff, lateral=lateral, tilt=np.radians(tilt_deg))
    scene.set_vehicle_velocity(model, data, drift, np.radians(tumble_deg))
    return run_trial(model, data, CaptureController(model), **kw)


def test_tilt_sets_the_pin_axis_error(model):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=0.6, lateral=(0.04, -0.02), tilt=(np.radians(3.0), 0.0))
    assert scene.pin_axis_error(model, data) == pytest.approx(np.radians(3.0), abs=1e-9)
    # tilting pivots about the pin tip, so the tip stays where it was asked to be
    assert scene.pin_offset(model, data) == pytest.approx([0.04, -0.02, 0.6], abs=1e-9)


def test_drift_is_the_centre_of_mass_velocity(model):
    data = mujoco.MjData(model)
    scene.reset(model, data, standoff=0.6)
    scene.set_vehicle_velocity(model, data, drift=(0.01, -0.02, 0.005), tumble=(0.002, 0.001, -0.003))
    mujoco.mj_forward(model, data)
    mujoco.mj_subtreeVel(model, data)
    R_l = data.site("lee_mouth").xmat.reshape(3, 3)
    v_com = R_l.T @ data.subtree_linvel[model.body("vehicle").id]
    assert v_com == pytest.approx([0.01, -0.02, 0.005], abs=1e-9)


def test_captures_a_vehicle_at_rest(model):
    result = attempt(model)
    assert result.success
    assert result.phase is Phase.DONE


def test_captures_a_drifting_tumbling_misaligned_vehicle(model):
    result = attempt(
        model,
        lateral=(0.05, -0.03),
        tilt_deg=(2.0, -1.5),
        drift=(0.005, -0.003, 0.004),
        tumble_deg=(0.06, -0.08, 0.03),
    )
    assert result.success
    assert result.t_trigger < 60.0
    assert result.rel_speed < 1e-3


def test_a_vehicle_leaving_too_fast_is_never_grappled(model):
    result = attempt(model, drift=(0.0, 0.0, 0.3), max_time=60.0)
    assert not result.success
    assert result.t_trigger is None
    assert result.phase in (Phase.ALIGN, Phase.INSERT)
