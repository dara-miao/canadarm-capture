"""Milestone 4 checks: outcome labels, the out-of-reach abort, sensing, and batches."""

import csv

import mujoco
import numpy as np
import pytest

from capture import batch, scene
from capture.batch import Ranges, Scenario
from capture.controller import Phase
from capture.sensing import PinSensor, SensorConfig
from capture.trial import Outcome, classify


@pytest.fixture(scope="module")
def model():
    return scene.build_model(meshes=False)


SEATED = np.array([0.001, 0.0, -0.30])


@pytest.mark.parametrize(
    "phase, fired, offset, rel_speed, expected",
    [
        (Phase.DONE, True, SEATED, 0.0002, Outcome.CAPTURED),
        (Phase.DONE, True, SEATED, 0.02, Outcome.CAUGHT_NOT_RIGID),  # seated but still moving
        (Phase.DONE, True, np.array([0.03, 0.0, -0.27]), 0.0, Outcome.CAUGHT_NOT_RIGID),  # held, not seated
        (Phase.DONE, True, np.array([0.0, 0.0, 0.5]), 0.03, Outcome.MISSED),  # pin outside the cavity
        (Phase.GRAPPLE, True, SEATED, 0.0, Outcome.CAUGHT_NOT_RIGID),  # ran out of time mid-sequence
        (Phase.ABORTED, False, np.array([0.0, 0.0, 3.0]), 0.3, Outcome.OUT_OF_REACH),
        (Phase.ALIGN, False, np.array([0.0, 0.0, 0.4]), 0.0, Outcome.TIMED_OUT),
    ],
)
def test_classify(phase, fired, offset, rel_speed, expected):
    assert classify(phase, fired, offset, rel_speed) is expected


def test_a_fleeing_vehicle_ends_out_of_reach_with_the_arm_under_control(model):
    row = batch.run_scenario(model, Scenario(drift_z=0.5))
    assert row["outcome"] == Outcome.OUT_OF_REACH.value
    assert row["t_trigger"] == ""
    assert row["duration"] < 120.0  # it gives up; it does not run out the 180 s clock


def test_sensor_delay_reports_where_the_pin_was(model):
    data = mujoco.MjData(model)
    scene.reset(model, data)
    scene.set_vehicle_velocity(model, data, drift=(0.0, 0.0, 0.05))
    sensor = PinSensor(model, SensorConfig(delay=0.5))
    sensor.reset(data)
    truth = {}
    for _ in range(1000):  # 2 s
        mujoco.mj_step1(model, data)
        truth[round(data.time, 6)] = data.site("pin_tip").xpos.copy()
        obs = sensor.observe(data)
        mujoco.mj_step2(model, data)
    seen_at = round(data.time - model.opt.timestep - 0.5, 6)
    assert obs.tip == pytest.approx(truth[seen_at], abs=1e-6)
    # the pin has moved 2.5 cm since then
    assert np.linalg.norm(data.site("pin_tip").xpos - obs.tip) == pytest.approx(0.025, abs=0.001)


def test_sensor_noise_is_repeatable_and_the_right_size(model):
    data = mujoco.MjData(model)
    scene.reset(model, data)
    mujoco.mj_forward(model, data)
    true_tip = data.site("pin_tip").xpos.copy()

    def readings(seed):
        sensor = PinSensor(model, SensorConfig(pos_noise=0.01), seed=seed)
        sensor.reset(data)
        return np.array([sensor.observe(data).tip - true_tip for _ in range(2000)])

    a = readings(3)
    assert a == pytest.approx(readings(3))
    assert not np.allclose(a, readings(4))
    assert a.std() == pytest.approx(0.01, rel=0.1)


def test_capture_succeeds_with_noisy_delayed_sensing(model):
    scenario = Scenario(
        seed=1, lateral_x=0.05, tilt_x=0.05, drift_x=0.01, tumble_y=0.004,
        sensor_delay=0.5, sensor_rate=10.0, sensor_pos_noise=0.01, sensor_angle_noise=np.radians(1.0),
    )  # fmt: skip
    assert batch.run_scenario(model, scenario)["outcome"] == Outcome.CAPTURED.value


def test_sampling_is_repeatable_and_inside_its_limits():
    ranges = Ranges(sensor_delay=0.4)
    a, b = batch.sample(200, ranges, seed=7), batch.sample(200, ranges, seed=7)
    assert a == b
    assert a != batch.sample(200, ranges, seed=8)
    for s in a:
        assert np.hypot(s.lateral_x, s.lateral_y) <= ranges.lateral
        assert np.hypot(s.tilt_x, s.tilt_y) <= ranges.tilt
        assert np.linalg.norm([s.drift_x, s.drift_y, s.drift_z]) <= ranges.drift
        assert np.linalg.norm([s.tumble_x, s.tumble_y, s.tumble_z]) <= ranges.tumble
        assert s.sensor_delay == 0.4
    assert len({s.seed for s in a}) == 200


def test_batch_rows_round_trip_through_csv(tmp_path):
    scenarios = [Scenario(), Scenario(drift_z=0.5)]
    rows = batch.run_batch(scenarios, workers=1)
    assert [r["outcome"] for r in rows] == [Outcome.CAPTURED.value, Outcome.OUT_OF_REACH.value]
    path = tmp_path / "out.csv"
    batch.write_csv(rows, path)
    with path.open() as f:
        back = list(csv.DictReader(f))
    assert [r["outcome"] for r in back] == [r["outcome"] for r in rows]
    assert float(back[1]["drift_z"]) == 0.5
    assert "captured" in batch.summarise(rows)
