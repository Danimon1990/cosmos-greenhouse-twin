#!/usr/bin/env python3
"""
Define and assign UsdShade materials for greenhouse prims.
Creates 4 UsdPreviewSurface materials under /World/Looks and binds them to
the actual scene paths in greenhouse.usda (Structure/TunnelCover, Plants/Bed_*/Bed,
Plants/Bed_*/Plant_*, Plants/Walkways/Walkway_*). Uses OverridePrim so this layer
composes over the root. Sublayer greenhouse_looks.usda into greenhouse.usda to apply.
Uses pxr (Usd, UsdGeom, UsdShade, Sdf, Gf). Run from project root.
"""

import os

try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade
except ImportError:
    raise ImportError("pxr not found. Use a Python environment with USD (e.g. Omniverse).")

# Paths: match your scene (World/Environment/Greenhouse from root)
WORLD = "/World"
LOOKS = "/World/Looks"
BASE = "/World/Environment/Greenhouse"
STRUCTURE = BASE + "/Structure"
PLANTS = BASE + "/Plants"

# Prim paths in the composed stage (from structure.usda reference + plants.usda payload)
PLASTIC_COVER_PATH = STRUCTURE + "/TunnelCover"
BED_PATHS = [PLANTS + "/Bed_{:02d}/Bed".format(i) for i in range(1, 9)]           # Bed_01/Bed .. Bed_08/Bed
PLANT_PATHS = [PLANTS + "/Bed_{:02d}/Plant_{:02d}".format(i, i) for i in range(1, 9)]
WALKWAY_PATHS = [PLANTS + "/Walkways/Walkway_{:02d}".format(i) for i in range(1, 8)]


def _project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", ".."))


def _output_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse_looks.usda")


def _root_usda_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse.usda")


def create_material(stage, path, diffuse_color, roughness=0.5, metallic=0.0, opacity=1.0):
    """Create a UsdShade.Material with UsdPreviewSurface shader at path."""
    mat = UsdShade.Material.Define(stage, path)
    shader_path = path + "/UsdPreviewSurface"
    shader = UsdShade.Shader.Define(stage, shader_path)
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(diffuse_color)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat


def override_and_bind(stage, prim_path, material):
    """Create an override prim at path and bind the material (for sublayer composition)."""
    prim = stage.OverridePrim(prim_path)
    if prim and material:
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)


def main():
    out_path = _output_path()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    stage.SetMetadata("metersPerUnit", 1)
    stage.SetMetadata("upAxis", "Y")
    stage.DefinePrim(WORLD, "Scope")
    stage.SetDefaultPrim(stage.GetPrimAtPath(WORLD))

    # --- Materials under /World/Looks ---
    UsdGeom.Scope.Define(stage, LOOKS)
    soil_mat = create_material(
        stage, LOOKS + "/SoilMat",
        Gf.Vec3f(0.35, 0.22, 0.12), roughness=0.9, metallic=0.0
    )
    plant_mat = create_material(
        stage, LOOKS + "/PlantMat",
        Gf.Vec3f(0.15, 0.55, 0.20), roughness=0.6, metallic=0.0
    )
    path_mat = create_material(
        stage, LOOKS + "/PathMat",
        Gf.Vec3f(0.18, 0.10, 0.06), roughness=0.95, metallic=0.0
    )
    plastic_mat = create_material(
        stage, LOOKS + "/PlasticMat",
        Gf.Vec3f(0.85, 0.92, 1.0), roughness=0.15, metallic=0.0, opacity=0.5
    )

    # --- Bind by overriding prims at actual scene paths (so sublayer applies the look) ---
    override_and_bind(stage, PLASTIC_COVER_PATH, plastic_mat)
    for p in BED_PATHS:
        override_and_bind(stage, p, soil_mat)
    for p in PLANT_PATHS:
        override_and_bind(stage, p, plant_mat)
    for p in WALKWAY_PATHS:
        override_and_bind(stage, p, path_mat)

    stage.Save()
    print(f"Saved: {out_path}")
    print("  Materials: /World/Looks/SoilMat, PlantMat, PathMat, PlasticMat")
    print("  Bound to: Structure/TunnelCover, Plants/Bed_*/Bed, Plants/Bed_*/Plant_*, Plants/Walkways/Walkway_*")
    print("")
    print("To apply the looks: add greenhouse_looks.usda as a sublayer to greenhouse.usda.")
    print("  (Script can do this automatically next.)")


if __name__ == "__main__":
    main()
