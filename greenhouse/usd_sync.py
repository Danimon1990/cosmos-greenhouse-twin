"""
Read greenhouse_state.json and write values into live_state.usda.

Idempotent: safe to run every step. Creates attributes if missing.
Returns a small dict of what was updated for debugging.
"""

import json
from pathlib import Path

try:
    from pxr import Sdf, Usd
except ImportError as e:
    raise SystemExit(
        "pxr (OpenUSD) not found. Install with: pip install usd-core"
    ) from e

from usd_init import (
    ACTUATORS,
    BED_1,
    BED_2,
    BED_3,
    DEFAULT_USD_PATH,
    ENVIRONMENT,
    GREENHOUSE,
    GREENHOUSE_DIR,
)


def _set_attr(prim: Usd.Prim, name: str, type_name: Sdf.ValueTypeName, value) -> bool:
    """Set attribute; create if missing. Returns True if set."""
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, type_name)
    if not attr:
        return False
    attr.Set(value)
    return True


def sync(state_path: str | Path | None = None, usd_path: str | Path | None = None) -> dict:
    """
    Read JSON state from state_path and write to usd_path.
    Returns dict with keys like "environment", "actuators", "zones" and count of updated attrs.
    """
    state_path = Path(state_path or GREENHOUSE_DIR / "greenhouse_state.json").resolve()
    usd_path = Path(usd_path or DEFAULT_USD_PATH).resolve()

    if not state_path.exists():
        raise FileNotFoundError(f"State file not found: {state_path}")

    with open(state_path) as f:
        state = json.load(f)

    stage = Usd.Stage.Open(str(usd_path))
    if not stage:
        raise RuntimeError(f"Could not open stage: {usd_path}")

    updated = {"environment": 0, "actuators": 0, "zones": 0, "timestamp": False}

    # Timestamp on Greenhouse
    gh = stage.GetPrimAtPath(GREENHOUSE)
    if gh and _set_attr(gh, "timestamp", Sdf.ValueTypeNames.String, state.get("timestamp", "")):
        updated["timestamp"] = True

    # Environment
    env = stage.GetPrimAtPath(ENVIRONMENT)
    if env:
        e = state.get("environment", {})
        if _set_attr(env, "temperature_c", Sdf.ValueTypeNames.Double, float(e.get("temperature_c", 22))):
            updated["environment"] += 1
        if _set_attr(env, "humidity_percent", Sdf.ValueTypeNames.Double, float(e.get("humidity_percent", 55))):
            updated["environment"] += 1
        if _set_attr(env, "co2_ppm", Sdf.ValueTypeNames.Double, float(e.get("co2_ppm", 420))):
            updated["environment"] += 1
        if _set_attr(env, "light_lux", Sdf.ValueTypeNames.Double, float(e.get("light_lux", 8000))):
            updated["environment"] += 1

    # Actuators
    act = stage.GetPrimAtPath(ACTUATORS)
    if act:
        a = state.get("actuators", {})
        if _set_attr(act, "fan", Sdf.ValueTypeNames.Double, float(a.get("fan", 0))):
            updated["actuators"] += 1
        if _set_attr(act, "vent", Sdf.ValueTypeNames.Double, float(a.get("vent", 0))):
            updated["actuators"] += 1
        if _set_attr(act, "water_valve", Sdf.ValueTypeNames.Bool, bool(a.get("water_valve", False))):
            updated["actuators"] += 1

    # Zones -> bed_1, bed_2, bed_3
    zones = state.get("zones", [])
    bed_paths = [BED_1, BED_2, BED_3]
    for i, bed_path in enumerate(bed_paths):
        bed = stage.GetPrimAtPath(bed_path)
        if not bed or i >= len(zones):
            continue
        z = zones[i]
        if _set_attr(bed, "crop", Sdf.ValueTypeNames.String, str(z.get("crop", "lettuce"))):
            updated["zones"] += 1
        if _set_attr(bed, "soil_moisture", Sdf.ValueTypeNames.Double, float(z.get("soil_moisture", 0.5))):
            updated["zones"] += 1
        if _set_attr(bed, "plant_height_cm", Sdf.ValueTypeNames.Double, float(z.get("plant_height_cm", 12))):
            updated["zones"] += 1
        # health: JSON may be number or string
        health_val = z.get("health", "0.9")
        if isinstance(health_val, (int, float)):
            health_val = str(health_val)
        if _set_attr(bed, "health", Sdf.ValueTypeNames.String, health_val):
            updated["zones"] += 1

    stage.GetRootLayer().Save()
    return updated


if __name__ == "__main__":
    import sys
    try:
        result = sync()
        print("Updated:", result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
