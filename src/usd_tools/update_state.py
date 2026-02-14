#!/usr/bin/env python3
"""
Update live telemetry and actuator state by writing ONLY to usd/layers/live_state.usda.

Uses pxr (Usd, Sdf). Sets edit target to the live_state layer, then creates/updates
attributes on device and sensor prims. Saves only the live_state layer.

Run from project root (or any cwd; paths resolved from script location):
  python src/usd_tools/update_state.py --temp 28 --humidity 90 --fan 0.5
  python src/usd_tools/update_state.py --tick --last-updated "2026-02-10T12:00:00"
"""

import argparse
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


# Prim paths under /World/Environment/Greenhouse/Devices
PATH_SENSOR = "/World/Environment/Greenhouse/Devices/Sensor_01"
PATH_FAN = "/World/Environment/Greenhouse/Devices/Fan_01"
PATH_VENT = "/World/Environment/Greenhouse/Devices/Vent_01"
PATH_VALVE = "/World/Environment/Greenhouse/Devices/Valve_01"
PATH_DEVICES = "/World/Environment/Greenhouse/Devices"
PATH_PLANTS = "/World/Environment/Greenhouse/Plants"


def zone_id_to_prim_path(zone_id):
    """Convert zone id (e.g. B01-A, B04-B) to prim path. Returns None if invalid."""
    import re
    m = re.match(r"^B(\d{2})-([ABC])$", zone_id.strip().upper())
    if not m:
        return None
    bed_num = m.group(1)
    zone_letter = m.group(2)
    return f"{PATH_PLANTS}/Bed_{bed_num}/Zones/Zone_{zone_letter}"


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


def ensure_prim(stage, path):
    """Ensure prim exists at path (composed); return prim or None."""
    prim = stage.GetPrimAtPath(path)
    if prim and prim.IsValid():
        return prim
    return None


def set_float_attr(prim, name, value):
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float)
    if attr:
        attr.Set(value)
        return True
    return False


def set_bool_attr(prim, name, value):
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Bool)
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


def set_int_attr(prim, name, value):
    attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Int)
    if attr:
        attr.Set(value)
        return True
    return False


def main():
    ap = argparse.ArgumentParser(
        description="Update live telemetry and actuator state in usd/layers/live_state.usda"
    )
    ap.add_argument("--temp", type=float, metavar="FLOAT", help="sensor:temperatureC")
    ap.add_argument("--humidity", type=float, metavar="FLOAT", help="sensor:humidityPct")
    ap.add_argument("--soil", type=float, metavar="FLOAT", help="sensor:soilMoisturePct")
    ap.add_argument("--fan", type=float, metavar="FLOAT", help="device:power on Fan_01 (0..1)")
    ap.add_argument("--vent", type=float, metavar="FLOAT", help="device:position on Vent_01 (0..100)")
    ap.add_argument("--valve", type=float, metavar="FLOAT", help="device:flow on Valve_01 (0..1)")
    ap.add_argument("--enable-fan", action="store_true", help="set Fan_01 device:enabled = true")
    ap.add_argument("--disable-fan", action="store_true", help="set Fan_01 device:enabled = false")
    ap.add_argument("--enable-vent", action="store_true", help="set Vent_01 device:enabled = true")
    ap.add_argument("--disable-vent", action="store_true", help="set Vent_01 device:enabled = false")
    ap.add_argument("--enable-valve", action="store_true", help="set Valve_01 device:enabled = true")
    ap.add_argument("--disable-valve", action="store_true", help="set Valve_01 device:enabled = false")
    ap.add_argument("--tick", action="store_true", help="increment state:tick on Devices")
    ap.add_argument("--last-updated", type=str, metavar="STR", help="set state:lastUpdated on Devices")
    ap.add_argument("--zone", type=str, metavar="ID", help="zone id (e.g. B01-A, B03-C)")
    ap.add_argument("--zone-moisture", type=float, metavar="FLOAT", help="zone:soilMoisturePct")
    ap.add_argument("--zone-light", type=float, metavar="FLOAT", help="zone:lightPct")
    ap.add_argument("--zone-health", type=float, metavar="FLOAT", help="zone:healthScore (0..1)")
    ap.add_argument("--zone-status", type=str, metavar="STR", help="zone:status (ok|dry|wet|shaded|stressed)")

    args = ap.parse_args()

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
        print("Error: live_state.usda not found in layer stack. Add it as the last sublayer in greenhouse.usda.", file=sys.stderr)
        sys.exit(1)

    stage.SetEditTarget(Usd.EditTarget(live_layer))
    ident = live_layer.GetIdentifier() if hasattr(live_layer, "GetIdentifier") else str(live_layer)
    print(f"Writing to layer: {ident}")

    changes = []

    # Sensor
    sensor = ensure_prim(stage, PATH_SENSOR)
    if sensor is None:
        print(f"Error: Prim not found: {PATH_SENSOR}", file=sys.stderr)
        sys.exit(1)

    if args.temp is not None:
        if set_float_attr(sensor, "sensor:temperatureC", args.temp):
            changes.append(f"sensor:temperatureC = {args.temp}")
    if args.humidity is not None:
        if set_float_attr(sensor, "sensor:humidityPct", args.humidity):
            changes.append(f"sensor:humidityPct = {args.humidity}")
    if args.soil is not None:
        if set_float_attr(sensor, "sensor:soilMoisturePct", args.soil):
            changes.append(f"sensor:soilMoisturePct = {args.soil}")
    if args.last_updated is not None:
        if set_string_attr(sensor, "state:lastUpdated", args.last_updated):
            changes.append(f"state:lastUpdated = {args.last_updated!r}")
    if args.tick:
        attr = sensor.CreateAttribute("state:tick", Sdf.ValueTypeNames.Int)
        if attr:
            prev = attr.Get()
            next_val = (prev if prev is not None else 0) + 1
            attr.Set(next_val)
            changes.append(f"state:tick = {next_val} (incremented)")

    # Devices: state:tick and state:lastUpdated are in the spec on Sensor_01; we did above.
    # If we also want them on Devices (as in current live_state.usda), we can add.
    # Spec says "on Sensor_01" for tick and last-updated, so we only write to Sensor_01.

    # Fan
    fan = ensure_prim(stage, PATH_FAN)
    if fan is None:
        print(f"Error: Prim not found: {PATH_FAN}", file=sys.stderr)
        sys.exit(1)
    if args.fan is not None:
        if set_float_attr(fan, "device:power", args.fan):
            changes.append(f"Fan_01 device:power = {args.fan}")
    if args.enable_fan:
        if set_bool_attr(fan, "device:enabled", True):
            changes.append("Fan_01 device:enabled = true")
    if args.disable_fan:
        if set_bool_attr(fan, "device:enabled", False):
            changes.append("Fan_01 device:enabled = false")

    # Vent
    vent = ensure_prim(stage, PATH_VENT)
    if vent is None:
        print(f"Error: Prim not found: {PATH_VENT}", file=sys.stderr)
        sys.exit(1)
    if args.vent is not None:
        if set_float_attr(vent, "device:position", args.vent):
            changes.append(f"Vent_01 device:position = {args.vent}")
    if args.enable_vent:
        if set_bool_attr(vent, "device:enabled", True):
            changes.append("Vent_01 device:enabled = true")
    if args.disable_vent:
        if set_bool_attr(vent, "device:enabled", False):
            changes.append("Vent_01 device:enabled = false")

    # Valve
    valve = ensure_prim(stage, PATH_VALVE)
    if valve is None:
        print(f"Error: Prim not found: {PATH_VALVE}", file=sys.stderr)
        sys.exit(1)
    if args.valve is not None:
        if set_float_attr(valve, "device:flow", args.valve):
            changes.append(f"Valve_01 device:flow = {args.valve}")
    if args.enable_valve:
        if set_bool_attr(valve, "device:enabled", True):
            changes.append("Valve_01 device:enabled = true")
    if args.disable_valve:
        if set_bool_attr(valve, "device:enabled", False):
            changes.append("Valve_01 device:enabled = false")

    # Zone overrides (require --zone)
    if args.zone is not None:
        zone_path = zone_id_to_prim_path(args.zone)
        if zone_path is None:
            print(f"Error: Invalid zone id {args.zone!r}. Use format B01-A, B02-B, etc.", file=sys.stderr)
            sys.exit(1)
        zone_prim = ensure_prim(stage, zone_path)
        if zone_prim is None:
            print(f"Error: Zone prim not found: {zone_path}", file=sys.stderr)
            sys.exit(1)
        if args.zone_moisture is not None:
            if set_float_attr(zone_prim, "zone:soilMoisturePct", args.zone_moisture):
                changes.append(f"zone {args.zone} soilMoisturePct = {args.zone_moisture}")
        if args.zone_light is not None:
            if set_float_attr(zone_prim, "zone:lightPct", args.zone_light):
                changes.append(f"zone {args.zone} lightPct = {args.zone_light}")
        if args.zone_health is not None:
            if set_float_attr(zone_prim, "zone:healthScore", args.zone_health):
                changes.append(f"zone {args.zone} healthScore = {args.zone_health}")
        if args.zone_status is not None:
            if set_string_attr(zone_prim, "zone:status", args.zone_status):
                changes.append(f"zone {args.zone} status = {args.zone_status!r}")

    if not changes:
        print("No updates requested. Use --temp, --humidity, --fan, --zone B01-A --zone-moisture 22, etc.")
        return

    live_layer.Save()
    print("Updated:", ", ".join(changes))
    print("\nReload the stage in USD Composer to see changes.")


if __name__ == "__main__":
    main()
