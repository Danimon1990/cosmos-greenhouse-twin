#!/usr/bin/env python3
"""
Load the greenhouse root stage and print:
- Layer stack (with live_state.usda check)
- Prim tree
- Device and sensor attribute values
- Selected plantHealth variant on Plants

Uses pxr.Usd. Run from project root: python src/usd_tools/inspect_stage.py
"""

import os
import sys

try:
    from pxr import Usd
except ImportError:
    print("Error: pxr.Usd not found. Use a Python environment with USD (e.g. Omniverse).", file=sys.stderr)
    sys.exit(1)


def _project_root():
    """Resolve project root (cosmos-greenhouse-twin) from this script's location."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", ".."))


def _greenhouse_stage_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse.usda")


def print_layer_stack(stage):
    """Print the stage layer stack and indicate if live_state.usda is present."""
    print("=== Layer stack (weakest → strongest) ===\n")
    try:
        stack = stage.GetLayerStack()
    except Exception as e:
        print(f"  Error reading layer stack: {e}", file=sys.stderr)
        return
    if not stack:
        print("  (empty)")
        return
    live_state_found = False
    for i, layer in enumerate(stack):
        ident = layer.GetIdentifier() if hasattr(layer, "GetIdentifier") else str(layer)
        marker = ""
        if "live_state" in ident:
            live_state_found = True
            marker = "  <-- live state overrides (strongest)"
        print(f"  [{i}] {ident}{marker}")
    print()
    if live_state_found:
        print("  live_state.usda is present; dynamic device/sensor values come from this layer.")
    else:
        print("  Warning: live_state.usda not found in layer stack. Add it as the last sublayer in greenhouse.usda.")
    print()


def print_prim_tree(prim, indent=0):
    """Print prim path and type for prim and all descendants."""
    prefix = "  " * indent
    kind = prim.GetTypeName()
    print(f"{prefix}{prim.GetPath()} [{kind}]")
    for child in sorted(prim.GetChildren(), key=lambda p: str(p.GetPath())):
        print_prim_tree(child, indent + 1)


def print_device_sensor_state_values(prim):
    """Print device:*, sensor:*, and state:* attribute values for prim and descendants."""
    for attr in prim.GetAttributes():
        name = attr.GetName()
        if name.startswith("device:") or name.startswith("sensor:") or name.startswith("state:"):
            try:
                val = attr.Get()
            except Exception:
                val = "<error reading>"
            if val is not None:
                print(f"  {prim.GetPath()} {name} = {val}")
    for child in prim.GetChildren():
        print_device_sensor_state_values(child)


def print_plants_variant(stage, world_path):
    """Print selected plantHealth variant on /World/Environment/Greenhouse/Plants."""
    plants_path = world_path.AppendPath("Environment/Greenhouse/Plants")
    plants = stage.GetPrimAtPath(plants_path)
    if not plants or not plants.IsValid():
        print("  Warning: /World/Environment/Greenhouse/Plants prim not found.")
        return
    vs = plants.GetVariantSets()
    names = vs.GetNames()
    if not names:
        print("  No variant sets on Plants.")
        return
    print("  Variant set on /World/Environment/Greenhouse/Plants:")
    for name in names:
        vset = vs.GetVariantSet(name)
        sel = vset.GetVariantSelection()
        print(f"    plantHealth (selected) = \"{sel}\"")


def main():
    path = _greenhouse_stage_path()
    if not os.path.isfile(path):
        print(f"Error: Stage not found: {path}", file=sys.stderr)
        sys.exit(1)

    stage = Usd.Stage.Open(path)
    if not stage:
        print("Error: Failed to open stage.", file=sys.stderr)
        sys.exit(1)

    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        print("Warning: No defaultPrim on stage.", file=sys.stderr)
        default_prim = stage.GetPseudoRoot()
    if not default_prim or not default_prim.IsValid():
        print("Error: No valid root prim to inspect.", file=sys.stderr)
        sys.exit(1)

    print_layer_stack(stage)

    print("=== Prim tree (defaultPrim = World) ===\n")
    print_prim_tree(default_prim)

    print("\n=== Device, sensor, and state attribute values ===\n")
    print_device_sensor_state_values(default_prim)

    print("\n=== Variant: plantHealth on Plants ===\n")
    print_plants_variant(stage, default_prim.GetPath())


if __name__ == "__main__":
    main()
