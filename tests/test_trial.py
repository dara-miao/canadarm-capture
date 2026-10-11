"""Milestone 4 checks: outcome labels, the out-of-reach abort, sensing, and batches."""

import csv

import mujoco
import numpy as np
import pytest

from capture import batch, scene
from capture.batch import Ranges, Scenario
from capture.controller import CaptureController, Phase
from capture.sensing import PinSensor, SensorConfig
from capture import snare
from capture.trial import Outcome, classify, is_seated, run_trial


@pytest.fixture(scope="module")
def model():
    return scene.build_model(meshes=False)


SEATED = np.array([0.001, 0.0, -0.30])


OUTSIDE = np.array([0.0, 0.0, 0.5])
HELD_UNSEATED = np.array([0.03, 0.0, -0.27])


@pytest.mark.parametrize(
    "phase, fired, offset, engaged, seated, latched, retained, expected",
    [
        (Phase.DONE, True, SEATED, True, True, True, True, Outcome.CAPTURED),
        (Phase.DONE, True, SEATED, True, True, True, False, Outcome.CAUGHT_NOT_RIGID),  # failed the retention check
        (Phase.DONE, True, SEATED, True, True, False, False, Outcome.CAUGHT_NOT_RIGID),  # latches never engaged
        (Phase.DONE, True, HELD_UNSEATED, True, False, False, False, Outcome.CAUGHT_NOT_RIGID),
        (Phase.DONE, True, OUTSIDE, True, False, False, False, Outcome.LOST),  # snared, then pulled out
        (Phase.DONE, True, OUTSIDE, True, True, True, False, Outcome.LOST),  # levered out during the retention check
        (Phase.DONE, True, OUTSIDE, False, False, False, False, Outcome.MISSED),  # the snare closed on nothing
        (Phase.GRAPPLE, True, SEATED, True, False, False, False, Outcome.CAUGHT_NOT_RIGID),  # ran out of time
        (Phase.ABORTED, False, np.array([0.0, 0.0, 3.0]), False, False, False, False, Outcome.OUT_OF_REACH),
        (Phase.ALIGN, False, np.array([0.0, 0.0, 0.4]), False, False, False, False, Outcome.TIMED_OUT),
    ],
)
def test_classify(phase, fired, offset, engaged, seated, latched, retained, expected):
    assert classify(phase, fired, offset, engaged, seated, latched, retained) is expected


def test_seated_needs_the_trial_finished_and_the_pin_at_rest():
    assert is_seated(Phase.DONE, SEATED, 0.0002)
    assert not is_seated(Phase.DONE, SEATED, 0.02)  # still moving
    assert not is_seated(Phase.GRAPPLE, SEATED, 0.0)
    assert not is_seated(Phase.DONE, HELD_UNSEATED, 0.0)


def test_a_clean_capture_passes_every_stage(model):
    row = batch.run_scenario(model, Scenario(lateral_x=0.04, tilt_y=0.05, roll=0.15, drift_x=0.01))
    assert row["outcome"] == Outcome.CAPTURED.value
    assert (row["engaged"], row["seated"], row["latched"], row["retained"]) == (1, 1, 1, 1)
    assert row["catchable_time"] == pytest.approx(snare.CLOSE_TIME, abs=0.01)  # catchable throughout closing
    assert row["retention_tilt"] < np.radians(0.5)


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
        assert abs(s.roll) <= ranges.roll
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


def test_matched_sweep_changes_only_the_named_quantity():
    base = batch.sample(5, seed=3)
    swept = batch.matched_sweep(base, "drift", [0.01, 0.05])
    assert len(swept) == 10
    for original, slow, fast in zip(base, swept[:5], swept[5:]):
        direction = np.array([original.drift_x, original.drift_y, original.drift_z])
        direction /= np.linalg.norm(direction)
        assert np.array([slow.drift_x, slow.drift_y, slow.drift_z]) == pytest.approx(0.01 * direction)
        assert np.array([fast.drift_x, fast.drift_y, fast.drift_z]) == pytest.approx(0.05 * direction)
        for other in ("seed", "lateral_x", "tilt_y", "roll", "tumble_z", "sensor_delay"):
            assert getattr(slow, other) == getattr(fast, other) == getattr(original, other)
    assert batch.with_value(base[0], "sensor_delay", 0.4).sensor_delay == 0.4


def test_a_tilting_fixture_plate_is_levered_straight_not_thrown_off(model):
    # Scenario 4 of the harsh pilot batch: the vehicle tumbles at about 1.9 deg/s, so after
    # the snare closes the fixture plate tilts some 12 degrees and meets the rim. On the
    # wall boxes' tops that contact returned forces of up to 2 MN and threw the vehicle
    # off at 25 cm/s (build log, 2026-10-11). On the rim spheres pull-in straightens it.
    harsh = Ranges(
        drift=0.122, tumble=np.radians(2.0),
        sensor_delay=0.5, sensor_rate=10.0, sensor_pos_noise=0.01, sensor_angle_noise=np.radians(1.0),
    )  # fmt: skip
    s = batch.sample(60, harsh, seed=0)[4]
    data = mujoco.MjData(model)
    scene.reset(model, data, lateral=(s.lateral_x, s.lateral_y), tilt=(s.tilt_x, s.tilt_y), roll=s.roll)
    scene.set_vehicle_velocity(
        model, data, drift=(s.drift_x, s.drift_y, s.drift_z), tumble=(s.tumble_x, s.tumble_y, s.tumble_z)
    )
    sensor = PinSensor(
        model, SensorConfig(s.sensor_delay, s.sensor_rate, s.sensor_pos_noise, s.sensor_angle_noise), seed=s.seed
    )
    controller = CaptureController(model, sensor=sensor)
    vehicle = model.body("vehicle").id
    tilt, speed = [], []

    def after_step(d):
        if controller.t_trigger is not None:
            v = np.empty(6)
            mujoco.mj_objectVelocity(model, d, mujoco.mjtObj.mjOBJ_BODY, vehicle, v, 0)
            tilt.append(scene.pin_axis_error(model, d))
            speed.append(np.linalg.norm(v[3:]))

    result = run_trial(model, data, controller, after_step=after_step)
    assert np.degrees(max(tilt)) > 10  # the plate did tilt onto the rim
    assert max(speed) < 1.5 * speed[0]  # and nothing added energy to the vehicle
    assert result.outcome is Outcome.CAPTURED
