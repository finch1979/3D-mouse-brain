"""Deterministic tests for the Virtual Mouse Running-Wheel behavior layer.

The behavior layer is engineered (motor decoder, wheel physics, synthetic
theta-like LFP); these tests pin its math and the brain -> motor -> wheel
integration. Run:

    py -3.13 -m pytest tests/test_running_model.py -q
"""

import math

import pytest

from mouse_atlas.build.connectivity_data import load_connectivity, step_activity
from mouse_atlas.build.running_model import (
    RUNNING_MODEL_CONFIG,
    decode_motor,
    lfp_sample,
    motor_raw,
    noise_at,
    run_state,
    step_wheel,
    theta_amplitude,
    theta_frequency,
)

CFG = RUNNING_MODEL_CONFIG


# --- motor decoder ---------------------------------------------------------

def test_motor_zero_activity_gives_zero_drive():
    assert decode_motor({"MOp": 0.0, "MOs": 0.0}) == 0.0
    assert decode_motor({}) == 0.0


def test_motor_below_threshold_gives_zero_drive():
    t = CFG["motor_threshold"]
    assert decode_motor({"MOp": t * 0.5, "MOs": t * 0.5}) == 0.0


def test_motor_higher_activity_gives_higher_drive():
    low = decode_motor({"MOp": 0.1, "MOs": 0.1})
    high = decode_motor({"MOp": 0.8, "MOs": 0.8})
    assert high > low > 0.0


def test_motor_drive_stays_in_unit_range():
    for a in [0.0, 0.5, 1.0, 5.0]:
        d = decode_motor({"MOp": a, "MOs": a})
        assert 0.0 <= d <= 1.0
    assert decode_motor({"MOp": 1.0, "MOs": 1.0}) == 1.0


def test_motor_raw_is_the_documented_weighted_sum():
    assert motor_raw({"MOp": 0.4, "MOs": 0.8}) == pytest.approx(0.5 * 0.4 + 0.5 * 0.8)


def test_motor_uses_raw_not_display_scaling():
    """The decoder is linear in raw activity; a gamma display transform would
    not be. Feeding an already-gamma'd value must change the result."""
    raw = 0.04
    assert decode_motor({"MOp": raw, "MOs": raw}) != decode_motor(
        {"MOp": raw ** 0.45, "MOs": raw ** 0.45})


# --- wheel physics ---------------------------------------------------------

def test_wheel_zero_drive_does_not_accelerate():
    v, d, a = step_wheel(0.0, 0.0, 0.0, 0.0, 0.1)
    assert (v, d, a) == (0.0, 0.0, 0.0)


def test_wheel_positive_drive_accelerates():
    v, _d, _a = step_wheel(0.0, 0.0, 0.0, 1.0, 0.1)
    assert v > 0.0


def test_wheel_drag_slows_after_drive_removed():
    v = 5.0
    for _ in range(20):
        v, _d, _a = step_wheel(v, 0.0, 0.0, 0.0, 0.1)
    assert v < 5.0


def test_wheel_speed_never_exceeds_max():
    v = 0.0
    for _ in range(1000):
        v, _d, _a = step_wheel(v, 0.0, 0.0, 1.0, 0.1, {**CFG, "max_speed_cms": 5.0})
        assert v <= 5.0


def test_wheel_speed_never_negative():
    v = 0.0
    v, _d, _a = step_wheel(v, 0.0, 0.0, 0.0, 0.1)
    assert v >= 0.0
    v, _d, _a = step_wheel(-3.0, 0.0, 0.0, 0.0, 0.1)  # defensive
    assert v >= 0.0


def test_wheel_accelerates_gradually_not_jump():
    v, _d, _a = step_wheel(0.0, 0.0, 0.0, 1.0, 0.1)
    assert 0.0 < v < CFG["max_speed_cms"]


def test_wheel_state_labels():
    assert run_state(0.0, 1.0) == "STOPPED"
    assert run_state(5.0, 1.0) == "RUNNING"
    assert run_state(5.0, 0.0) == "COASTING"


# --- synthetic CA1 theta ---------------------------------------------------

def test_theta_frequency_finite_and_bounded():
    for v in [0.0, 5.0, 20.0, 100.0]:
        f = theta_frequency(v)
        assert math.isfinite(f)
        assert CFG["lfp"]["base_hz"] <= f <= CFG["lfp"]["base_hz"] + CFG["lfp"]["span_hz"]


def test_theta_frequency_increases_monotonically_with_speed():
    speeds = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
    freqs = [theta_frequency(v) for v in speeds]
    assert all(b > a for a, b in zip(freqs, freqs[1:]))


def test_theta_amplitude_increases_with_running_and_is_bounded():
    a0 = theta_amplitude(0.0)
    a1 = theta_amplitude(CFG["max_speed_cms"])
    assert a0 == pytest.approx(CFG["lfp"]["amp_base"])
    assert a1 == pytest.approx(CFG["lfp"]["amp_base"] + CFG["lfp"]["amp_span"])
    assert a0 < a1


def test_noise_is_reproducible_and_small():
    assert noise_at(7) == noise_at(7)
    assert noise_at(7) != noise_at(8)
    assert all(-1.0 <= noise_at(i) <= 1.0 for i in range(50))


def test_lfp_sample_is_reproducible():
    a = lfp_sample(1.234, 12.0, 100)
    b = lfp_sample(1.234, 12.0, 100)
    assert a == b
    assert math.isfinite(a[0]) and math.isfinite(a[1])


# --- integration: brain -> motor -> wheel ----------------------------------

def _activity(doc):
    return [0.0] * len(doc["nodes"])


def test_button_cue_alone_does_not_move_the_wheel():
    """Setting the run cue must not set velocity; only physics integration can."""
    doc = load_connectivity("allen")
    activity = _activity(doc)
    # cue present in the network input, but no brain step and no wheel step run
    assert decode_motor({n["acronym"]: activity[i] for i, n in enumerate(doc["nodes"])}) == 0.0
    v, _d, _a = step_wheel(0.0, 0.0, 0.0, 0.0, 0.1)
    assert v == 0.0


def test_brain_activity_drives_motor_and_motor_drives_wheel():
    doc = load_connectivity("allen")
    activity = _activity(doc)
    # no cue: motor stays 0 and wheel does not accelerate
    drive0 = decode_motor({n["acronym"]: activity[i] for i, n in enumerate(doc["nodes"])})
    v0, _d, _a = step_wheel(0.0, 0.0, 0.0, drive0, 0.1)
    assert drive0 == 0.0 and v0 == 0.0

    # sustained engineered cue at MOp/MOs, stepped through the existing model
    cue = {r: CFG["run_cue_input"] for r in CFG["motor_regions"]}
    for _ in range(8):
        activity = step_activity(doc, activity, input_activity=cue, steps=1)
    as_dict = {n["acronym"]: activity[i] for i, n in enumerate(doc["nodes"])}
    drive1 = decode_motor(as_dict)
    assert as_dict["MOp"] > 0.0 and as_dict["MOs"] > 0.0
    assert drive1 > 0.0
    v1, _d, _a = step_wheel(0.0, 0.0, 0.0, drive1, 0.1)
    assert v1 > 0.0


def test_decay_when_cue_removed_and_reset_to_initial():
    doc = load_connectivity("allen")
    activity = _activity(doc)
    cue = {r: CFG["run_cue_input"] for r in CFG["motor_regions"]}
    for _ in range(8):
        activity = step_activity(doc, activity, input_activity=cue, steps=1)
    assert max(activity) > 0.0
    # remove cue, let it decay
    for _ in range(20):
        activity = step_activity(doc, activity, input_activity=None, steps=1)
    # reset restores the documented all-zero initial state
    activity = _activity(doc)
    v, d, a = 0.0, 0.0, 0.0
    assert max(activity) == 0.0
    assert (v, d, a) == (0.0, 0.0, 0.0)
