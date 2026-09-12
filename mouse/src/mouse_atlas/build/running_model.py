"""Engineered behavior layer for the Virtual Mouse Running-Wheel prototype.

These models are ENGINEERED / MODEL ASSUMPTIONS layered on top of the real
Allen connectivity graph. They are NOT derived from the Allen projection data,
NOT fitted to real mouse physiology, and NOT a claim that region activity
encodes real wheel speed. See the project wording rules:

    Neural activity   region-level connectivity model (measured edges)
    Motor output      engineered decoder from MOp/MOs activity (a readout)
    Wheel             simple virtual first-order physics
    CA1 signal        synthetic theta-like LFP visualization

Four systems are kept separate: neural activity, motor decoder, wheel physics,
and synthetic electrophysiology. Nothing here may read a display-normalized
value; only RAW region activity enters the decoder. The JS viewer mirrors these
exact formulas so the browser and the tests agree.
"""

from __future__ import annotations

import math

# One place for every magic number. Values are suggested prototype starting
# points, not measurements.
RUNNING_MODEL_CONFIG = {
    "motor_regions": ["MOp", "MOs"],
    "motor_weights": {"MOp": 0.5, "MOs": 0.5},
    "motor_threshold": 0.05,
    "max_speed_cms": 30.0,
    "drive_gain": 20.0,       # engine strength (cm/s^2 per unit motor drive)
    "drag": 1.5,              # first-order drag (1/s)
    "wheel_radius_cm": 8.0,   # display wheel radius
    "run_cue_input": 1.0,     # injected per brain step while "Start running"
    "brain_step_hz": 8.0,     # network diffusion step rate
    "stop_speed_eps": 0.2,    # below this speed the wheel reads as stopped
    "lfp": {
        "base_hz": 6.0,
        "span_hz": 3.0,
        "half_sat_cms": 10.0,
        "amp_base": 0.3,
        "amp_span": 0.7,
        "noise_amp": 0.02,
        "seed": 1234,
    },
}


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def motor_raw(activity, config: dict = RUNNING_MODEL_CONFIG) -> float:
    """Uncompressed weighted motor activity (before threshold/compression).

    `activity` maps region acronym -> RAW activity value (a dict in tests; the
    JS uses a typed array + region index, with the same weights).
    """
    return sum(weight * float(activity.get(region, 0.0))
               for region, weight in config["motor_weights"].items())


def decode_motor(activity, config: dict = RUNNING_MODEL_CONFIG) -> float:
    """Engineered motor drive in [0, 1] from RAW region activity.

    motorRaw = sum(weight_r * rawActivity[r]); then a threshold and linear
    compression. This is a BCI-like readout, not a motor-cortex measurement.
    """
    threshold = config["motor_threshold"]
    return clamp((motor_raw(activity, config) - threshold) / (1.0 - threshold), 0.0, 1.0)


def step_wheel(velocity: float, distance: float, angle: float, motor_drive: float,
               dt: float, config: dict = RUNNING_MODEL_CONFIG):
    """One first-order wheel physics step. Returns (velocity, distance, angle).

    acceleration = drive_gain*motorDrive - drag*velocity, integrated with dt,
    velocity clamped to [0, max_speed]. The wheel therefore accelerates
    gradually and coasts down under drag; the button never sets speed directly.
    """
    acceleration = config["drive_gain"] * motor_drive - config["drag"] * velocity
    velocity = clamp(velocity + acceleration * dt, 0.0, config["max_speed_cms"])
    distance = distance + velocity * dt
    angle = angle + (velocity / config["wheel_radius_cm"]) * dt
    return velocity, distance, angle


def theta_frequency(speed_cms: float, config: dict = RUNNING_MODEL_CONFIG) -> float:
    """Synthetic theta-like frequency (Hz) as a function of wheel speed.

    Model mapping (NOT experimentally fitted):
        f = base + span * v / (v + half_sat)
    ~6 Hz at rest, rising toward base+span as speed grows.
    """
    lfp = config["lfp"]
    speed = max(0.0, float(speed_cms))
    return lfp["base_hz"] + lfp["span_hz"] * speed / (speed + lfp["half_sat_cms"])


def theta_amplitude(speed_cms: float, config: dict = RUNNING_MODEL_CONFIG) -> float:
    """Synthetic theta-like amplitude, mildly increasing with running."""
    lfp = config["lfp"]
    s = clamp(float(speed_cms) / config["max_speed_cms"], 0.0, 1.0)
    return lfp["amp_base"] + lfp["amp_span"] * s


def noise_at(index: int, config: dict = RUNNING_MODEL_CONFIG) -> float:
    """Small reproducible pseudo-noise in [-1, 1) from a sample index.

    Hash-based (no PRNG state), so the same index and seed always give the
    same value on every platform and in the mirrored JS.
    """
    x = math.sin((index + 1) * 12.9898 + config["lfp"]["seed"] * 0.001) * 43758.5453
    frac = x - math.floor(x)
    return frac * 2.0 - 1.0


def lfp_sample(phase: float, speed_cms: float, index: int,
               config: dict = RUNNING_MODEL_CONFIG):
    """Return (value, frequency_hz) for a synthetic CA1 LFP-like sample.

    LFP = amplitude * sin(phase) + noise_amp * noise(index).
    """
    freq = theta_frequency(speed_cms, config)
    amplitude = theta_amplitude(speed_cms, config)
    value = amplitude * math.sin(phase) + config["lfp"]["noise_amp"] * noise_at(index, config)
    return value, freq


def run_state(velocity: float, cue: float,
              config: dict = RUNNING_MODEL_CONFIG) -> str:
    if velocity <= config["stop_speed_eps"]:
        return "STOPPED"
    return "RUNNING" if cue > 0 else "COASTING"
