#!/usr/bin/env python3
"""
Update plant materials based on zone health status.

When a zone is marked as "dry" or "stressed", all plants in that zone
switch to UnhealthyPlantMat. When the zone is "ok", plants revert to PlantMat.

This creates visual feedback in the digital twin that mirrors the spatial
reasoning - judges can SEE which zone is problematic.

Usage:
  # Set plants in zone B03-C to unhealthy (dry zone)
  python src/usd_tools/update_plant_health.py --zone B03-C --status dry

  # Restore plants in zone B03-C to healthy
  python src/usd_tools/update_plant_health.py --zone B03-C --status ok

  # Update all zones based on current live_state.usda status values
  python src/usd_tools/update_plant_health.py --sync
"""

import argparse
import os
import re
import sys

try:
    from pxr import Sdf, Usd, UsdShade
    _HAS_PXR = True
except ImportError:
    _HAS_PXR = False
    print("Error: pxr (USD) not found.", file=sys.stderr)
    sys.exit(1)


def _project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(script_dir))


def _greenhouse_stage_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse.usda")


# Material paths
MAT_HEALTHY = "/World/Looks/PlantMat"
MAT_UNHEALTHY = "/World/Looks/UnhealthyPlantMat"

# Zone boundaries (Z coordinate thresholds)
# Each bed is 16m long (Z from -8 to +8), divided into 3 zones of ~5.33m each
ZONE_A_MAX_Z = -2.67  # Zone_A: Z < -2.67
ZONE_B_MAX_Z = 2.67   # Zone_B: -2.67 <= Z <= 2.67
                       # Zone_C: Z > 2.67

# Plant layout: Row A starts at Z=-7.0, Row B at Z=-6.8, step=0.4m
ROW_A_START_Z = -7.0
ROW_B_START_Z = -6.8
PLANT_SPACING = 0.4


def find_live_state_layer(stage):
    """Return the live_state.usda layer from the stage's layer stack."""
    try:
        stack = stage.GetLayerStack()
    except Exception:
        return None
    for layer in stack:
        ident = layer.GetIdentifier() if hasattr(layer, "GetIdentifier") else str(layer)
        if "live_state.usda" in ident:
            return layer
    return None


def parse_zone_id(zone_id: str):
    """Parse zone ID (e.g., B03-C) into (bed_num, zone_letter)."""
    m = re.match(r"^B(\d{2})-([ABC])$", zone_id.strip().upper())
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def get_zone_z_range(zone_letter: str) -> tuple[float, float]:
    """Return (min_z, max_z) for a zone letter."""
    if zone_letter == "A":
        return -8.0, ZONE_A_MAX_Z
    elif zone_letter == "B":
        return ZONE_A_MAX_Z, ZONE_B_MAX_Z
    else:  # C
        return ZONE_B_MAX_Z, 8.0


def get_plants_in_zone(stage, bed_num: int, zone_letter: str) -> list[str]:
    """
    Return list of plant prim paths that are in the given zone.

    Plants are located based on their Z coordinate relative to zone boundaries.
    """
    bed_path = f"/World/Environment/Greenhouse/Plants/Bed_{bed_num:02d}"
    bed_prim = stage.GetPrimAtPath(bed_path)
    if not bed_prim or not bed_prim.IsValid():
        return []

    min_z, max_z = get_zone_z_range(zone_letter)
    plants_in_zone = []

    for child in bed_prim.GetChildren():
        name = child.GetName()
        # Match plant names: Plant_NN, Plant_NN_A_XXX, Plant_NN_B_XXX
        if not name.startswith("Plant_"):
            continue

        # Get the plant's Z position from its transform
        xform_attr = child.GetAttribute("xformOp:transform")
        if not xform_attr:
            continue

        transform = xform_attr.Get()
        if transform is None:
            continue

        # Extract Z translation from the 4x4 matrix (row 3, column 2 in 0-indexed)
        # Matrix is row-major: ((r0c0,r0c1,r0c2,r0c3), (r1c0,...), ...)
        # Translation is in the 4th row (index 3)
        z_pos = transform[3][2]

        # Check if plant is in this zone
        if min_z <= z_pos < max_z or (zone_letter == "C" and z_pos >= max_z - 0.1):
            plants_in_zone.append(child.GetPath().pathString)

    return plants_in_zone


def update_plant_materials(stage, live_layer, plant_paths: list[str], healthy: bool) -> int:
    """
    Update material bindings for the given plants.

    Returns count of plants updated.
    """
    material_path = MAT_HEALTHY if healthy else MAT_UNHEALTHY
    count = 0

    for plant_path in plant_paths:
        prim = stage.GetPrimAtPath(plant_path)
        if not prim or not prim.IsValid():
            continue

        # Get or create the material binding relationship
        # We use UsdShade.MaterialBindingAPI for proper USD semantics
        binding_api = UsdShade.MaterialBindingAPI(prim)
        material = UsdShade.Material.Get(stage, material_path)

        if material:
            binding_api.Bind(material)
            count += 1

    return count


def get_zone_status(stage, bed_num: int, zone_letter: str) -> str:
    """Get the current status of a zone from live_state."""
    zone_path = f"/World/Environment/Greenhouse/Plants/Bed_{bed_num:02d}/Zones/Zone_{zone_letter}"
    prim = stage.GetPrimAtPath(zone_path)
    if not prim or not prim.IsValid():
        return "ok"

    status_attr = prim.GetAttribute("zone:status")
    if status_attr:
        val = status_attr.Get()
        if val:
            return str(val)
    return "ok"


def sync_all_zones(stage, live_layer) -> list[str]:
    """
    Sync plant materials for all zones based on their current status.

    Returns list of actions taken.
    """
    actions = []

    for bed_num in range(1, 9):
        for zone_letter in ["A", "B", "C"]:
            status = get_zone_status(stage, bed_num, zone_letter)
            healthy = status == "ok"

            plants = get_plants_in_zone(stage, bed_num, zone_letter)
            if plants:
                count = update_plant_materials(stage, live_layer, plants, healthy)
                zone_id = f"B{bed_num:02d}-{zone_letter}"
                mat_name = "PlantMat" if healthy else "UnhealthyPlantMat"
                actions.append(f"{zone_id}: {count} plants → {mat_name} (status={status})")

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Update plant materials based on zone health status"
    )
    parser.add_argument("--zone", type=str, help="Zone ID (e.g., B03-C)")
    parser.add_argument("--status", type=str, choices=["ok", "dry", "wet", "shaded", "stressed"],
                        help="Zone status (determines healthy/unhealthy material)")
    parser.add_argument("--sync", action="store_true",
                        help="Sync all zones: update plant materials based on current zone:status values")
    parser.add_argument("--list", action="store_true",
                        help="List plants in a zone (use with --zone)")

    args = parser.parse_args()

    if not args.zone and not args.sync:
        print("Error: Specify --zone ID or --sync", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    stage_path = _greenhouse_stage_path()
    if not os.path.isfile(stage_path):
        print(f"Error: Stage not found: {stage_path}", file=sys.stderr)
        sys.exit(1)

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("Error: Failed to open stage", file=sys.stderr)
        sys.exit(1)

    live_layer = find_live_state_layer(stage)
    if not live_layer:
        print("Error: live_state.usda not found in layer stack", file=sys.stderr)
        sys.exit(1)

    # Set edit target to live_state layer
    stage.SetEditTarget(Usd.EditTarget(live_layer))
    print(f"Writing to: {live_layer.GetIdentifier()}")

    if args.sync:
        print("\nSyncing all zones...")
        actions = sync_all_zones(stage, live_layer)
        for a in actions:
            print(f"  {a}")
        live_layer.Save()
        print(f"\nUpdated {len(actions)} zones. Reload stage in USD Composer to see changes.")
        return

    # Single zone update
    bed_num, zone_letter = parse_zone_id(args.zone)
    if bed_num is None:
        print(f"Error: Invalid zone ID '{args.zone}'. Use format B01-A, B03-C, etc.", file=sys.stderr)
        sys.exit(1)

    plants = get_plants_in_zone(stage, bed_num, zone_letter)
    print(f"\nZone {args.zone}: {len(plants)} plants found")

    if args.list:
        for p in plants[:10]:  # Show first 10
            print(f"  {p}")
        if len(plants) > 10:
            print(f"  ... and {len(plants) - 10} more")
        return

    if not args.status:
        print("Error: Specify --status (ok, dry, wet, shaded, stressed)", file=sys.stderr)
        sys.exit(1)

    healthy = args.status == "ok"
    count = update_plant_materials(stage, live_layer, plants, healthy)

    mat_name = "PlantMat" if healthy else "UnhealthyPlantMat"
    print(f"Updated {count} plants to {mat_name}")

    # Also update the zone status attribute
    zone_path = f"/World/Environment/Greenhouse/Plants/Bed_{bed_num:02d}/Zones/Zone_{zone_letter}"
    zone_prim = stage.GetPrimAtPath(zone_path)
    if zone_prim and zone_prim.IsValid():
        status_attr = zone_prim.CreateAttribute("zone:status", Sdf.ValueTypeNames.String)
        if status_attr:
            status_attr.Set(args.status)
            print(f"Set {args.zone} zone:status = '{args.status}'")

    live_layer.Save()
    print("\nReload stage in USD Composer to see changes.")


if __name__ == "__main__":
    main()
