#!/usr/bin/env python3
"""
Day 6 & 7: Cosmos Integration with Actuation.

Reads sensor/device snapshot from the USD stage and a camera image,
sends both to Cosmos Reason 2 (or uses mock when API not configured),
logs explanation + recommendations, and optionally EXECUTES actions (Day 7).

Usage (from project root):
  # Dry run (log only, no changes):
  python src/agent/cosmos_agent.py --image demo/frame.png

  # Full actuation (apply recommendations to live_state.usda):
  python src/agent/cosmos_agent.py --image demo/frame.png --actuate

With USD (local): reads context from usd/root/greenhouse.usda.
Without USD (e.g. cloud instance): use --context-file or default context.
  python src/agent/cosmos_agent.py --image demo/frame.png --context-file context.json
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime

try:
    from pxr import Sdf, Usd, UsdShade
    _HAS_PXR = True
except ImportError:
    _HAS_PXR = False

from cosmos_client import COSMOS_API_URL, COSMOS_API_KEY, call_cosmos, is_configured
from schema import ContextPayload

# Default context when no USD and no --context-file (e.g. run on cloud without pxr)
DEFAULT_CONTEXT: ContextPayload = {
    "sensors": {"temperatureC": 22.0, "humidityPct": 50.0, "soilMoisturePct": 40.0},
    "devices": {"fanPower": 0.0, "ventPosition": 0.0, "valveFlow": 0.0},
}

# Stage paths (same as simple_agent)
PATH_SENSOR = "/World/Environment/Greenhouse/Devices/Sensor_01"
PATH_FAN = "/World/Environment/Greenhouse/Devices/Fan_01"
PATH_VENT = "/World/Environment/Greenhouse/Devices/Vent_01"
PATH_VALVE = "/World/Environment/Greenhouse/Devices/Valve_01"


def _project_root() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(script_dir))


def _greenhouse_stage_path() -> str:
    return os.path.join(_project_root(), "usd", "root", "greenhouse.usda")


def _logs_dir() -> str:
    d = os.path.join(_project_root(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def get_float(prim, name: str, default: float | None = None) -> float:
    attr = prim.GetAttribute(name)
    if attr:
        val = attr.Get()
        return float(val) if val is not None else (default if default is not None else 0.0)
    return default if default is not None else 0.0


def get_string(prim, name: str, default: str = "") -> str:
    """Get string attribute value from prim."""
    attr = prim.GetAttribute(name)
    if attr:
        val = attr.Get()
        return str(val) if val is not None else default
    return default


def read_zone_data(stage) -> list[dict]:
    """Read all zone data for spatial reasoning context."""
    zones = []
    plants_path = "/World/Environment/Greenhouse/Plants"

    for bed_num in range(1, 9):
        for zone_letter in ["A", "B", "C"]:
            zone_path = f"{plants_path}/Bed_{bed_num:02d}/Zones/Zone_{zone_letter}"
            prim = stage.GetPrimAtPath(zone_path)
            if prim and prim.IsValid():
                zone_id = f"B{bed_num:02d}-{zone_letter}"
                zones.append({
                    "zoneId": zone_id,
                    "bedNumber": bed_num,
                    "position": zone_letter,  # A=north, B=center, C=south
                    "soilMoisturePct": get_float(prim, "zone:soilMoisturePct", 40.0),
                    "lightPct": get_float(prim, "zone:lightPct", 70.0),
                    "healthScore": get_float(prim, "zone:healthScore", 0.8),
                    "status": get_string(prim, "zone:status", "ok"),
                })
    return zones


def read_snapshot(stage_path: str) -> ContextPayload:
    """Load stage and return sensor + device + zone context for spatial reasoning."""
    stage = Usd.Stage.Open(stage_path)
    if not stage:
        raise RuntimeError("Failed to open stage")

    sensor = stage.GetPrimAtPath(PATH_SENSOR)
    fan = stage.GetPrimAtPath(PATH_FAN)
    vent = stage.GetPrimAtPath(PATH_VENT)
    valve = stage.GetPrimAtPath(PATH_VALVE)

    for name, prim in [("Sensor_01", sensor), ("Fan_01", fan), ("Vent_01", vent), ("Valve_01", valve)]:
        if not prim or not prim.IsValid():
            raise RuntimeError(f"Prim not found: {name}")

    # Read zone data for spatial reasoning
    zones = read_zone_data(stage)

    # Find problematic zones for summary
    dry_zones = [z["zoneId"] for z in zones if z["status"] == "dry"]
    shaded_zones = [z["zoneId"] for z in zones if z["status"] == "shaded"]

    return {
        "sensors": {
            "temperatureC": get_float(sensor, "sensor:temperatureC", 22.0),
            "humidityPct": get_float(sensor, "sensor:humidityPct", 50.0),
            "soilMoisturePct": get_float(sensor, "sensor:soilMoisturePct", 40.0),
        },
        "devices": {
            "fanPower": get_float(fan, "device:power", 0.0),
            "ventPosition": get_float(vent, "device:position", 0.0),
            "valveFlow": get_float(valve, "device:flow", 0.0),
        },
        "zones": zones,
        "alerts": {
            "dryZones": dry_zones,
            "shadedZones": shaded_zones,
        },
    }


def load_image_base64(path: str) -> str:
    """Read image file and return base64-encoded string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# ─────────────────────────────────────────────────────────────────────────────
# Day 7: Actuation - Apply recommendations to live_state.usda
# ─────────────────────────────────────────────────────────────────────────────

def find_live_state_layer(stage):
    """Return the layer in the stage's layer stack whose identifier contains 'live_state.usda'."""
    try:
        stack = stage.GetLayerStack()
    except Exception:
        return None
    for layer in stack:
        ident = layer.GetIdentifier() if hasattr(layer, "GetIdentifier") else str(layer)
        if "live_state.usda" in ident:
            return layer
    return None


def set_float_attr(prim, name: str, value: float) -> bool:
    """Create or update a float attribute on a prim."""
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float)
    if attr:
        attr.Set(value)
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Plant Health Visual Feedback - Update materials based on zone status
# ─────────────────────────────────────────────────────────────────────────────

PATH_PLANTS = "/World/Environment/Greenhouse/Plants"
MAT_HEALTHY = "/World/Looks/PlantMat"
MAT_UNHEALTHY = "/World/Looks/UnhealthyPlantMat"

# Zone Z boundaries (bed is 16m, split into 3 zones of ~5.33m each)
ZONE_A_MAX_Z = -2.67
ZONE_B_MAX_Z = 2.67


def get_zone_z_range(zone_letter: str) -> tuple[float, float]:
    """Return (min_z, max_z) for a zone letter."""
    if zone_letter == "A":
        return -8.0, ZONE_A_MAX_Z
    elif zone_letter == "B":
        return ZONE_A_MAX_Z, ZONE_B_MAX_Z
    else:  # C
        return ZONE_B_MAX_Z, 8.0


def get_plants_in_zone(stage, bed_num: int, zone_letter: str) -> list:
    """Return list of plant prims in the given zone based on Z position."""
    bed_path = f"{PATH_PLANTS}/Bed_{bed_num:02d}"
    bed_prim = stage.GetPrimAtPath(bed_path)
    if not bed_prim or not bed_prim.IsValid():
        return []

    min_z, max_z = get_zone_z_range(zone_letter)
    plants = []

    for child in bed_prim.GetChildren():
        name = child.GetName()
        if not name.startswith("Plant_"):
            continue

        xform_attr = child.GetAttribute("xformOp:transform")
        if not xform_attr:
            continue

        transform = xform_attr.Get()
        if transform is None:
            continue

        z_pos = transform[3][2]  # Translation Z from 4x4 matrix

        if min_z <= z_pos < max_z or (zone_letter == "C" and z_pos >= max_z - 0.1):
            plants.append(child)

    return plants


def sync_plant_materials(stage, live_layer) -> list[str]:
    """
    Update plant materials based on zone status values.

    Zones with status != "ok" get UnhealthyPlantMat (brownish).
    Zones with status == "ok" get PlantMat (green).

    Returns list of actions for logging.
    """
    actions = []

    for bed_num in range(1, 9):
        for zone_letter in ["A", "B", "C"]:
            zone_path = f"{PATH_PLANTS}/Bed_{bed_num:02d}/Zones/Zone_{zone_letter}"
            zone_prim = stage.GetPrimAtPath(zone_path)

            status = "ok"
            if zone_prim and zone_prim.IsValid():
                status_attr = zone_prim.GetAttribute("zone:status")
                if status_attr:
                    val = status_attr.Get()
                    if val:
                        status = str(val)

            # Only update unhealthy zones to minimize changes
            if status != "ok":
                healthy = False
                material_path = MAT_UNHEALTHY
            else:
                healthy = True
                material_path = MAT_HEALTHY

            plants = get_plants_in_zone(stage, bed_num, zone_letter)
            material = UsdShade.Material.Get(stage, material_path)

            if plants and material:
                for plant_prim in plants:
                    binding_api = UsdShade.MaterialBindingAPI(plant_prim)
                    binding_api.Bind(material)

                zone_id = f"B{bed_num:02d}-{zone_letter}"
                mat_name = "PlantMat" if healthy else "UnhealthyPlantMat"
                if status != "ok":
                    actions.append(f"{zone_id}: {len(plants)} plants → {mat_name} (status={status})")

    return actions


def apply_recommendations(stage_path: str, recommendations: list[dict]) -> list[str]:
    """
    Apply Cosmos recommendations to live_state.usda.

    Returns list of actions taken (for logging/display).
    """
    if not _HAS_PXR:
        return ["Skipped: pxr (USD) not available"]

    if not os.path.isfile(stage_path):
        return [f"Skipped: Stage not found: {stage_path}"]

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        return ["Skipped: Failed to open stage"]

    live_layer = find_live_state_layer(stage)
    if not live_layer:
        return ["Skipped: live_state.usda not found in layer stack"]

    # Set edit target to live_state layer (all writes go there)
    stage.SetEditTarget(Usd.EditTarget(live_layer))

    actions_taken = []

    for rec in recommendations:
        action = rec.get("action", "")
        value = rec.get("value")
        confidence = rec.get("confidence", 0.0)

        # Skip low-confidence or no-action recommendations
        if action == "no_action" or action == "send_alert":
            actions_taken.append(f"{action}: {rec.get('why', 'no reason')}")
            continue

        if value is None:
            continue

        # Apply actuator changes
        if action == "set_fan":
            prim = stage.GetPrimAtPath(PATH_FAN)
            if prim and prim.IsValid():
                set_float_attr(prim, "device:power", float(value))
                actions_taken.append(f"Fan_01 device:power = {value}")

        elif action == "set_vent":
            prim = stage.GetPrimAtPath(PATH_VENT)
            if prim and prim.IsValid():
                set_float_attr(prim, "device:position", float(value))
                actions_taken.append(f"Vent_01 device:position = {value}")

        elif action == "set_valve":
            prim = stage.GetPrimAtPath(PATH_VALVE)
            if prim and prim.IsValid():
                set_float_attr(prim, "device:flow", float(value))
                actions_taken.append(f"Valve_01 device:flow = {value}")

    # Update timestamp
    from datetime import datetime
    sensor = stage.GetPrimAtPath(PATH_SENSOR)
    if sensor and sensor.IsValid():
        ts_attr = sensor.CreateAttribute("state:lastUpdated", Sdf.ValueTypeNames.String)
        if ts_attr:
            ts_attr.Set(datetime.utcnow().isoformat() + "Z")
        tick_attr = sensor.CreateAttribute("state:tick", Sdf.ValueTypeNames.Int)
        if tick_attr:
            prev = tick_attr.Get() or 0
            tick_attr.Set(prev + 1)
            actions_taken.append(f"state:tick = {prev + 1}")

    # Sync plant materials based on zone status (visual feedback)
    plant_actions = sync_plant_materials(stage, live_layer)
    actions_taken.extend(plant_actions)

    # Save only the live_state layer
    if actions_taken:
        live_layer.Save()
        actions_taken.append(f"Saved: {live_layer.GetIdentifier()}")

    return actions_taken


def main() -> None:
    parser = argparse.ArgumentParser(description="Cosmos agent: image + USD context → explanation + recommendations + optional actuation")
    parser.add_argument("--image", required=True, help="Path to PNG/JPG frame (e.g. demo/frame.png)")
    parser.add_argument("--stage", default=None, help="Path to greenhouse.usda (default: usd/root/greenhouse.usda)")
    parser.add_argument("--context-file", default=None, help="JSON file with sensors/devices context (use when pxr not available, e.g. on cloud)")
    parser.add_argument("--actuate", action="store_true", help="Day 7: Apply recommendations to live_state.usda (default: log only)")
    args = parser.parse_args()

    root = _project_root()
    stage_path = args.stage or _greenhouse_stage_path()
    image_path = args.image if os.path.isabs(args.image) else os.path.join(root, args.image)

    if not os.path.isfile(image_path):
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    # Get context: from USD stage, from --context-file, or default (no USD)
    if args.context_file:
        context_path = args.context_file if os.path.isabs(args.context_file) else os.path.join(root, args.context_file)
        if not os.path.isfile(context_path):
            print(f"Error: Context file not found: {context_path}", file=sys.stderr)
            sys.exit(1)
        with open(context_path) as f:
            context = json.load(f)
        print("Using context from --context-file")
    elif _HAS_PXR and os.path.isfile(stage_path):
        context = read_snapshot(stage_path)
    else:
        if not _HAS_PXR:
            print("Note: pxr (USD) not found; using default context. Use --context-file to supply sensor/device JSON.", file=sys.stderr)
        else:
            print(f"Note: Stage not found: {stage_path}; using default context.", file=sys.stderr)
        context = DEFAULT_CONTEXT
    image_b64 = load_image_base64(image_path)

    if not is_configured():
        print("DRY RUN: COSMOS_API_URL or COSMOS_API_KEY not set; using mock response.")

    payload, raw = call_cosmos(context, image_b64)

    log_dir = _logs_dir()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"run_{ts}.json")
    log_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "image_path": image_path,
        "sensor_snapshot": context,
        "explanation": payload.get("explanation", ""),
        "recommendations": payload.get("recommendations", []),
    }
    if raw is not None:
        log_data["raw_model_response"] = raw

    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)

    print(f"Log written: {log_path}")
    print("\n--- Summary ---")
    print(payload.get("explanation", "(no explanation)")[:500])
    if payload.get("explanation") and len(payload["explanation"]) > 500:
        print("...")
    recs = payload.get("recommendations") or []
    print(f"\nRecommendations ({len(recs)}):")
    for r in recs:
        action = r.get("action", "?")
        value = r.get("value")
        why = r.get("why", "")
        print(f"  - {action}" + (f" = {value}" if value is not None else "") + f"  // {why}")

    # ─────────────────────────────────────────────────────────────────────────
    # Day 7: Actuation
    # ─────────────────────────────────────────────────────────────────────────
    if args.actuate:
        print("\n--- Actuation (Day 7) ---")
        actions = apply_recommendations(stage_path, recs)
        if actions:
            for a in actions:
                print(f"  ✓ {a}")
            print("\nReload the stage in USD Composer to see changes.")
        else:
            print("  No actions applied.")
    else:
        print("\n(Dry run: use --actuate to apply recommendations to live_state.usda)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise
