#!/usr/bin/env python3
"""
Write usd/layers/demo_dry_zone.usda: override layer that sets zone B03-C to dry
and all plants in that zone to UnhealthyPlantMat. Use this for the video "dry zone"
shot so the plants visibly turn brown regardless of viewer binding resolution.

Usage (from project root):
  python scripts/write_demo_dry_layer.py

Then open usd/root/greenhouse_dry_demo.usda in USD Composer for the dry-zone shot.
"""

import os
import sys

try:
    from pxr import Sdf, Usd
except ImportError:
    print("Error: pxr (USD) not found. Install usd-core or use Omniverse Python.", file=sys.stderr)
    sys.exit(1)


def _project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def _stage_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse.usda")


# Zone C: Z > 2.67
ZONE_C_MIN_Z = 2.67


def get_plant_paths_in_zone_c(stage, bed_num: int) -> list[str]:
    """Return plant prim paths in Bed bed_num, Zone C (Z > 2.67)."""
    bed_path = f"/World/Environment/Greenhouse/Plants/Bed_{bed_num:02d}"
    bed = stage.GetPrimAtPath(bed_path)
    if not bed or not bed.IsValid():
        return []

    paths = []
    for child in bed.GetChildren():
        name = child.GetName()
        if not name.startswith("Plant_"):
            continue
        xform = child.GetAttribute("xformOp:transform")
        if not xform:
            continue
        t = xform.Get()
        if t is None:
            continue
        z = t[3][2]
        if z >= ZONE_C_MIN_Z - 0.01:
            paths.append(child.GetPath().pathString)
    return paths


def main():
    root = _project_root()
    stage_path = _stage_path()
    if not os.path.isfile(stage_path):
        print(f"Error: Stage not found: {stage_path}", file=sys.stderr)
        sys.exit(1)

    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print("Error: Failed to open stage.", file=sys.stderr)
        sys.exit(1)

    # B03-C = Bed 3, Zone C
    plant_paths = get_plant_paths_in_zone_c(stage, 3)
    if not plant_paths:
        print("Warning: No plants found in B03-C. Check stage.", file=sys.stderr)

    # Build USDA content: over World/.../Plants/Bed_03/Zones/Zone_C (dry) + each plant → UnhealthyPlantMat
    lines = [
        '#usda 1.0',
        '(',
        '    doc = "Video demo: B03-C dry zone. Override only. Strongest when used as top sublayer."',
        '    metersPerUnit = 1',
        '    upAxis = "Y"',
        ')',
        '',
        'over "World"',
        '{',
        '    over "Environment"',
        '    {',
        '        over "Greenhouse"',
        '        {',
        '            over "Plants"',
        '            {',
        '                over "Bed_03"',
        '                {',
        '                    over "Zones"',
        '                    {',
        '                        over "Zone_C"',
        '                        {',
        '                            float zone:healthScore = 0.5',
        '                            string zone:id = "B03-C"',
        '                            float zone:lightPct = 70',
        '                            float zone:soilMoisturePct = 22',
        '                            string zone:status = "dry"',
        '                        }',
        '                    }',
        '',
    ]

    for path in sorted(plant_paths):
        # path is like /World/Environment/Greenhouse/Plants/Bed_03/Plant_03_C_012
        name = path.split("/")[-1]
        lines.append(f'                    over "{name}"')
        lines.append('                    {')
        lines.append('                        rel material:binding = </World/Looks/UnhealthyPlantMat> (')
        lines.append('                            bindMaterialAs = "strongerThanDescendants"')
        lines.append('                        )')
        lines.append('                    }')
        lines.append('')

    lines.extend([
        '                }',
        '            }',
        '        }',
        '    }',
        '}',
        '',
    ])

    out_path = os.path.join(root, "usd", "layers", "demo_dry_zone.usda")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {len(plant_paths)} plant overrides to {out_path}")
    print("For the video: open usd/root/greenhouse_dry_demo.usda to see B03-C plants as brown.")


if __name__ == "__main__":
    main()
