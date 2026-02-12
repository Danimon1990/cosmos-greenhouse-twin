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
    soil = get_float(sensor, "sensor:soilMoisturePct", 40.0)

    print(f"Editing layer: {live_layer.GetIdentifier() if hasattr(live_layer, 'GetIdentifier') else live_layer}")
    print(f"Sensor (composed): humidity={humidity}%, soilMoisture={soil}%")

    # Set edit target so all writes go to live_state only
    stage.SetEditTarget(Usd.EditTarget(live_layer))

    actions = []

    # Rule 1: humidity > 80 → fan 0.4, else 0
    if humidity > 80:
        set_float_attr(fan, "device:power", 0.4)
        actions.append(f"Humidity {humidity}% → Fan set to 0.4")
        # Optional: open vent slightly
        set_float_attr(vent, "device:position", 20.0)
        actions.append("Vent set to 20 (humidity high)")
    else:
        set_float_attr(fan, "device:power", 0.0)
        actions.append(f"Humidity {humidity}% → Fan set to 0.0")

    # Rule 2: soil < 30 → valve 1, else 0
    if soil < 30:
        set_float_attr(valve, "device:flow", 1.0)
        actions.append(f"Soil {soil}% → Valve opened (1.0)")
    else:
        set_float_attr(valve, "device:flow", 0.0)
        actions.append(f"Soil {soil}% → Valve closed (0.0)")

    # Increment state:tick on Sensor_01 (create if missing)
    tick_attr = sensor.CreateAttribute("state:tick", Sdf.ValueTypeNames.Int)
    if tick_attr:
        prev = tick_attr.Get()
        next_tick = (prev if prev is not None else 0) + 1
        tick_attr.Set(next_tick)
        actions.append(f"state:tick = {next_tick}")

    live_layer.Save()

    for a in actions:
        print(a)
    print("\nReload the stage in USD Composer to see changes.")


if __name__ == "__main__":
    main()
