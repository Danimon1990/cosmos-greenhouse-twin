#!/usr/bin/env python
"""
Populate each greenhouse bed with two staggered rows of plant instances.

Layout per bed (local bed space):
- Bed dimensions: 0.8 m wide (X), 16 m long (Z), 0.4 m high (see plants.usda comment).
- Usable planting band along Z: [-7.0, +7.0] (1 m clear at each end).
- Row A: x = -0.2 m, plants every 0.4 m along Z in [-7.0, +7.0].
- Row B: x = +0.2 m, plants every 0.4 m along Z, offset by 0.2 m (diagonal / staggered).

Implementation notes:
- We use regular USD prims (no PointInstancer) so each plant remains individually addressable.
- We keep the existing Bed_NN/Plant_NN prim in each bed and reuse it as one of the plants
  so that the existing plant_health variants (plant_states.usda) keep working.
- The script is idempotent: re-running it will remove any extra Plant_* children under each bed
  and regenerate the rows, keeping only Plant_NN as the "representative" prim.

Run from anywhere (path is resolved from script location):

  python src/usd_tools/populate_bed_plants.py
"""

import os

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

# Resolve paths relative to project root so the script works from any cwd
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
STAGE_PATH = os.path.join(_PROJECT_ROOT, "usd", "components", "plants.usda")
PLANT_ASSET_PATH = "../assets/plant_sprout/plant_sprout_abstract.usda"
PLANT_ASSET_PRIM_PATH = "/Mesh"

# Vertical offset so plants sit on the bed surface (bed top ~0.4 m)
PLANT_Y = 0.39

# Bed planting layout (40 cm between plants)
ROW_OFFSETS_X = {"A": -0.2, "B": 0.2}
Z_START_A = -7.0
Z_END_A = 7.0
Z_STEP = 0.4

# Row B offset by half a step for diagonal/stagger
Z_OFFSET_B = 0.2


def _iter_beds(plants_root_prim):
    """Yield (bed_number_int, bed_prim) for all Bed_XX children under /Plants."""
    for child in plants_root_prim.GetChildren():
        name = child.GetName()
        if not name.startswith("Bed_"):
            continue
        try:
            num = int(name.split("_", 1)[1])
        except ValueError:
            continue
        yield num, child


def _get_or_create_template_plant(stage, bed_prim, bed_num):
    """
    Ensure there is a Bed_NN/Plant_NN prim and return it.

    If it exists, we reuse it. If not, we create it with the same reference
    and material binding pattern we use for generated plants.
    """
    plant_name = f"Plant_{bed_num:02d}"
    plant_path = bed_prim.GetPath().AppendChild(plant_name)
    plant_prim = stage.GetPrimAtPath(plant_path)

    if not plant_prim or not plant_prim.IsValid():
        plant_prim = stage.DefinePrim(plant_path, "Xform")

        # Add reference to the plant asset
        refs = plant_prim.GetReferences()
        refs.ClearReferences()
        refs.AddReference(PLANT_ASSET_PATH, PLANT_ASSET_PRIM_PATH)

        # Mark as non-instanceable (we want per-plant bindings/states)
        plant_prim.SetInstanceable(False)

        # Bind to PlantMat material at the root stage path
        mat_api = UsdShade.MaterialBindingAPI.Apply(plant_prim)
        rel = mat_api.GetDirectBindingRel()
        rel.SetTargets([Sdf.Path("/World/Looks/PlantMat")])

    return plant_prim


def _clear_existing_plants(stage, bed_prim, template_plant_prim):
    """
    Remove any Plant_* children under the bed except the template plant.
    This keeps the script idempotent.
    """
    template_path = template_plant_prim.GetPath()
    children = list(bed_prim.GetChildren())
    for child in children:
        if not child.GetName().startswith("Plant_"):
            continue
        if child.GetPath() == template_path:
            continue
        stage.RemovePrim(child.GetPath())


def _set_plant_transform(plant_prim, x, y, z):
    """Set a transform on the plant prim to position it (USD-version-safe)."""
    xformable = UsdGeom.Xformable(plant_prim)

    # Try to reuse an existing transform op if one is present; this keeps us
    # compatible with USD versions that don't expose RemoveXformOp.
    ops = xformable.GetOrderedXformOps()
    op = None
    if ops:
        # Use the first op if it's a transform, otherwise fall back to adding one
        if ops[0].GetOpType() == UsdGeom.XformOp.TypeTransform:
            op = ops[0]

    if op is None:
        op = xformable.AddTransformOp()

    m = Gf.Matrix4d(1.0)
    m.SetTranslate(Gf.Vec3d(x, y, z))
    op.Set(m)


def _create_extra_plant(stage, bed_prim, bed_num, row_label, index, x, z):
    """
    Create a new plant prim under a bed with a consistent naming scheme and
    standard reference/material binding.

    We use type "Mesh" (not "Xform") so the prim matches the referenced asset
    and renderers (usdview Hydra Storm, Omniverse) actually draw it. Xform
    prims with referenced geometry often get skipped by draw traversal.
    """
    name = f"Plant_{bed_num:02d}_{row_label}_{index:03d}"
    prim_path = bed_prim.GetPath().AppendChild(name)
    plant_prim = stage.DefinePrim(prim_path, "Mesh")

    # Reference to the shared plant asset (brings in points, faceVertexIndices, etc.)
    refs = plant_prim.GetReferences()
    refs.ClearReferences()
    refs.AddReference(PLANT_ASSET_PATH, PLANT_ASSET_PRIM_PATH)

    plant_prim.SetInstanceable(False)

    # Bind to PlantMat (green) from greenhouse_looks.usda; green shows when stage includes that layer
    mat_api = UsdShade.MaterialBindingAPI.Apply(plant_prim)
    rel = mat_api.GetDirectBindingRel()
    rel.SetTargets([Sdf.Path("/World/Looks/PlantMat")])

    _set_plant_transform(plant_prim, x, PLANT_Y, z)


def populate_beds(stage):
    plants_root = stage.GetPrimAtPath("/World/Environment/Greenhouse/Plants")
    if not plants_root or not plants_root.IsValid():
        raise RuntimeError("Could not find /World/Environment/Greenhouse/Plants in stage.")

    for bed_num, bed_prim in _iter_beds(plants_root):
        print(f"Populating Bed_{bed_num:02d}")
        template = _get_or_create_template_plant(stage, bed_prim, bed_num)

        # Remove any old generated plants so we can regenerate deterministically
        _clear_existing_plants(stage, bed_prim, template)

        # Row A: x = -0.2, z from -7.0 to +7.0 inclusive
        x_a = ROW_OFFSETS_X["A"]
        num_steps_a = int(round((Z_END_A - Z_START_A) / Z_STEP)) + 1
        center_used = False
        idx_a = 0
        for i in range(num_steps_a):
            z = Z_START_A + i * Z_STEP

            # Use the template plant for the central position (z ~ 0) so variants keep working
            if not center_used and abs(z) < 1e-6:
                _set_plant_transform(template, x_a, PLANT_Y, z)
                center_used = True
                continue

            _create_extra_plant(stage, bed_prim, bed_num, "A", idx_a, x_a, z)
            idx_a += 1

        # Row B: x = +0.2, same span but offset by half a step
        x_b = ROW_OFFSETS_X["B"]
        z_start_b = Z_START_A + Z_OFFSET_B
        z_end_b = Z_END_A - Z_OFFSET_B
        num_steps_b = int(round((z_end_b - z_start_b) / Z_STEP)) + 1

        for i in range(num_steps_b):
            z = z_start_b + i * Z_STEP
            _create_extra_plant(stage, bed_prim, bed_num, "B", i, x_b, z)


def main():
    stage = Usd.Stage.Open(STAGE_PATH)
    if not stage:
        raise RuntimeError(f"Failed to open stage at {STAGE_PATH}")

    populate_beds(stage)

    print(f"Saving populated beds to {STAGE_PATH}")
    stage.GetRootLayer().Save()


if __name__ == "__main__":
    main()

