#!/usr/bin/env python3
"""
Load the greenhouse root stage and print the prim tree and sensor/device attributes.
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


def print_prim_tree(prim, indent=0):
    """Print prim path and type for prim and all descendants."""
    prefix = "  " * indent
    kind = prim.GetTypeName()
    print(f"{prefix}{prim.GetPath()} [{kind}]")
    for child in sorted(prim.GetChildren(), key=lambda p: str(p.GetPath())):
        print_prim_tree(child, indent + 1)


def print_sensor_and_device_values(prim):
    """Print device:* and sensor:* attribute values for prim and descendants."""
    for attr in prim.GetAttributes():
        name = attr.GetName()
        if name.startswith("device:") or name.startswith("sensor:"):
            val = attr.Get()
            if val is not None:
                print(f"  {prim.GetPath()} {name} = {val}")
    for child in prim.GetChildren():
        print_sensor_and_device_values(child)


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
        print("Warning: No defaultPrim on stage.")
        default_prim = stage.GetPseudoRoot()

    print("=== Prim tree (defaultPrim = World) ===\n")
    print_prim_tree(default_prim)

    print("\n=== Sensor and device attribute values ===\n")
    print_sensor_and_device_values(default_prim)

    # Optionally print variant set on Plants
    plants_path = default_prim.GetPath().AppendPath("Environment/Greenhouse/Plants")
    plants = stage.GetPrimAtPath(plants_path)
    if plants and plants.IsValid():
        vs = plants.GetVariantSets()
        if vs.GetNames():
            print("\n=== Variant set on /World/Environment/Greenhouse/Plants ===")
            for name in vs.GetNames():
                vset = vs.GetVariantSet(name)
                print(f"  variantSet {name}: selected = \"{vset.GetVariantSelection()}\"")


if __name__ == "__main__":
    main()
