"""
Greenhouse state simulation: sensor drift, soil drying, and watering effect.

Uses only Python 3.10+ stdlib. Modifies state in place; keeps all values bounded.
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path


# Bounds and drift parameters
TEMP_DRIFT = 0.3
HUMIDITY_DRIFT = 1.5
SOIL_DRY_RATE = 0.008
SOIL_WET_GAIN = 0.15
RANDOM_SEED = 42

random.seed(RANDOM_SEED)


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp value to [low, high]."""
    return max(low, min(high, value))


def _load_state(path: Path) -> dict:
    """Load state from JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def _save_state(path: Path, state: dict) -> None:
    """Save state to JSON file."""
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def step(state: dict, state_path: Path | None = None) -> None:
    """
    Advance simulation one step: drift env, dry soil, apply watering if valve is on.

    Modifies state in place. If state_path is given, reads from file first and
    writes back after (caller can pass state without path for in-memory only).
    """
    if state_path is not None:
        state.clear()
        state.update(_load_state(state_path))

    state["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    env = state["environment"]
    zones = state["zones"]
    actuators = state["actuators"]

    # Drift temperature and humidity
    env["temperature_c"] = _clamp(
        env["temperature_c"] + random.uniform(-TEMP_DRIFT, TEMP_DRIFT),
        10.0,
        40.0,
    )
    env["humidity_percent"] = _clamp(
        env["humidity_percent"] + random.uniform(-HUMIDITY_DRIFT, HUMIDITY_DRIFT),
        0.0,
        100.0,
    )
    # Optional: slight drift for co2 and light (keep bounded)
    env["co2_ppm"] = _clamp(env.get("co2_ppm", 420) + random.uniform(-5, 5), 300, 2000)
    env["light_lux"] = _clamp(env.get("light_lux", 8000) + random.uniform(-100, 100), 0, 50000)

    # Soil drying and watering
    water_valve = actuators.get("water_valve", False)
    for zone in zones:
        zone["soil_moisture"] = _clamp(zone["soil_moisture"] - SOIL_DRY_RATE, 0.0, 1.0)
        if water_valve:
            zone["soil_moisture"] = _clamp(zone["soil_moisture"] + SOIL_WET_GAIN, 0.0, 1.0)
    # After applying watering, turn valve off (one-shot per step)
    if water_valve:
        actuators["water_valve"] = False

    if state_path is not None:
        _save_state(state_path, state)


def load_state(path: Path) -> dict:
    """Load full state from JSON file."""
    return _load_state(path)


def save_state(path: Path, state: dict) -> None:
    """Write state to JSON file."""
    _save_state(path, state)
