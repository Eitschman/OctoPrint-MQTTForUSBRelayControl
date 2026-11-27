"""Validate command timing at both settings and runtime boundaries."""

import math

COMMAND_TIMING_RANGES = {"command_max_age": (1, 60), "command_min_interval": (0.1, 10)}


def validate_command_timing(key, value):
    minimum, maximum = COMMAND_TIMING_RANGES[key]
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{key} must be a finite number from {minimum} to {maximum} seconds")
    return float(value)
