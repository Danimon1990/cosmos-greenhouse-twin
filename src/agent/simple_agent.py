#!/usr/bin/env python3
"""
Simple rule-based agent for the OpenUSD greenhouse digital twin.

Reads sensor values from the composed stage, applies threshold rules,
and writes actuator updates only to usd/layers/live_state.usda.
Represents a closed-loop control step before Cosmos integration.

Run from project root (no arguments):
  python src/agent/simple_agent.py

Reload the stage in USD Composer to see actuator changes.
"""

import os
import sys

try:
    from pxr import Sdf, Usd
except ImportError:
    print("Error: pxr (Usd, Sdf) not found. Use a Python environment with USD.", file=sys.stderr)
    sys.exit(1)


def _project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(script_dir))


def _greenhouse_stage_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse.usda")


PATH_SENSOR = "/World/Environment/Greenhouse/Devices/Sensor_01"
PATH_FAN = "/World/Environment/Greenhouse/Devices/Fan_01"
PATH_VENT = "/World/Environment/Greenhouse/Devices/Vent_01"
PATH_VALVE = "/World/Environment/Greenhouse/Devices/Valve_01"


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


def get_prim(stage, path):
    prim = stage.GetPrimAtPath(path)
    if prim and prim.IsValid():
        return prim
    return None


def get_float(prim, name, default=None):
    attr = prim.GetAttribute(name)
    if attr:
        val = attr.Get()
        return val if val is not None else default
    return default


def get_string(prim, name, default=None):
    attr = prim.GetAttribute(name)
    if attr:
        val = attr.Get()
        return val if val is not None else default
    return default


def set_float_attr(prim, name, value):
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float)
    if attr:
        attr.Set(value)
        return True
    return False


def set_int_attr(prim, name, value):
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Int)
    if attr:
        attr.Set(value)
        return True
    return False


def set_string_attr(prim, name, value):
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.String)
    if attr:
        attr.Set(value)
        return True
    return False


PATH_PLANTS = "/World/Environment/Greenhouse/Plants"


def iter_zone_prims(stage):
    """Yield (prim, bed_name, zone_name) for each Zone_A/B/C under Plants."""
    plants = stage.GetPrimAtPath(PATH_PLANTS)
    if not plants or not plants.IsValid():
        return
    for bed in sorted(plants.GetChildren(), key=lambda p: p.GetName()):
        if not bed.GetName().startswith("Bed_"):
            continue
        zones_prim = stage.GetPrimAtPath(bed.GetPath().AppendPath("Zones"))
        if not zones_prim or not zones_prim.IsValid():
            continue
        for zone_name in ["Zone_A", "Zone_B", "Zone_C"]:
            zone = stage.GetPrimAtPath(zones_prim.GetPath().AppendPath(zone_name))
            if zone and zone.IsValid():
                yield zone, bed.GetName(), zone_name


def main():
    stage_path = _greenhouse_stage_path()
    if not os.path.isfile(stage_path):
        print(f"Error: Stage not found: {stage_path}", file=sys.stderr)
        sys.exit(1)

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("Error: Failed to open stage.", file=sys.stderr)
        sys.exit(1)

    live_layer = find_live_state_layer(stage)
    if not live_layer:
        print("Error: live_state.usda not found in layer stack.", file=sys.stderr)
        sys.exit(1)

    sensor = get_prim(stage, PATH_SENSOR)
    fan = get_prim(stage, PATH_FAN)
    vent = get_prim(stage, PATH_VENT)
    valve = get_prim(stage, PATH_VALVE)

    for name, prim in [("Sensor_01", sensor), ("Fan_01", fan), ("Vent_01", vent), ("Valve_01", valve)]:
        if prim is None:
            print(f"Error: Prim not found: /World/Environment/Greenhouse/Devices/{name}", file=sys.stderr)
            sys.exit(1)

    # Read composed sensor values (from any layer)
    humidity = get_float(sensor, "sensor:humidityPct", 50.0)

    print(f"Editing layer: {live_layer.GetIdentifier() if hasattr(live_layer, 'GetIdentifier') else live_layer}")
    print(f"Sensor (composed): humidity={humidity}%")

    # Set edit target so all writes go to live_state only
    stage.SetEditTarget(Usd.EditTarget(live_layer))

    actions = []

    # Rule 1: humidity > 80 → fan 0.4, vent 20; else fan 0
    if humidity > 80:
        set_float_attr(fan, "device:power", 0.4)
        set_float_attr(vent, "device:position", 20.0)
        actions.append(f"Humidity {humidity}% → Fan 0.4, Vent 20")
    else:
        set_float_attr(fan, "device:power", 0.0)
        actions.append(f"Humidity {humidity}% → Fan 0")

    # Rule 2: per-zone soil moisture and light; dry → valve 1 and mark status; shaded = annotate only
    dry_zones = []
    for zone_prim, bed_name, zone_name in iter_zone_prims(stage):
        moisture = get_float(zone_prim, "zone:soilMoisturePct", 40.0)
        light = get_float(zone_prim, "zone:lightPct", 70.0)
        if moisture < 30:
            set_string_attr(zone_prim, "zone:status", "dry")
            dry_zones.append(f"{bed_name}/{zone_name}")
        elif light < 40:
            set_string_attr(zone_prim, "zone:status", "shaded")

    if dry_zones:
        set_float_attr(valve, "device:flow", 1.0)
        actions.append(f"Dry zones ({len(dry_zones)}): {', '.join(dry_zones)} → Valve 1")
    else:
        set_float_attr(valve, "device:flow", 0.0)
        actions.append("No dry zones → Valve 0")

    # Increment state:tick on Sensor_01 (create if missing)
    tick_attr = sensor.CreateAttribute("state:tick", Sdf.ValueTypeNames.Int)
    if tick_attr:
        prev = tick_attr.Get()
        next_tick = (prev if prev is not None else 0) + 1
        tick_attr.Set(next_tick)
        actions.append(f"state:tick = {next_tick}")

    live_layer.Save()

    # Summary
    print("\n--- Summary ---")
    print(f"Dry zones: {len(dry_zones)}")
    if dry_zones:
        print(f"  {', '.join(dry_zones)}")
    for a in actions:
        print(a)
    print("\nReload the stage in USD Composer to see changes.")


if __name__ == "__main__":
    main()
