#!/usr/bin/env python
"""Build the production plant point-instancer override used by greenhouse_main."""

import os
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_PATH = os.path.join(ROOT, "usd", "source", "blender", "greenhouse_exchange.usdc")
OUTPUT_PATH = os.path.join(ROOT, "usd", "layouts", "plants.usda")
ASSET_PATH = "../assets/plant_sprout/plant_sprout_abstract.usda"


def main():
    source = Usd.Stage.Open(SOURCE_PATH)
    output = Usd.Stage.CreateNew(OUTPUT_PATH)
    output.SetMetadata("metersPerUnit", 1.0)
    output.SetMetadata("upAxis", "Y")
    output.GetRootLayer().documentation = (
        "Strong production override: replaces Blender plant marker meshes "
        "with bed-level point instances of the sprout asset."
    )

    plants_path = Sdf.Path("/World/Environment/Greenhouse/Plants")
    source_plants = source.GetPrimAtPath(plants_path)
    output.OverridePrim("/World")
    output.OverridePrim("/World/Environment")
    output.OverridePrim("/World/Environment/Greenhouse")
    output.OverridePrim(plants_path)

    material = UsdShade.Material.Define(
        output, "/World/Looks/PlantSproutMat"
    )
    shader = UsdShade.Shader.Define(
        output, "/World/Looks/PlantSproutMat/PreviewSurface"
    )
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput(
        "diffuseColor", Sdf.ValueTypeNames.Color3f
    ).Set(Gf.Vec3f(0.15, 0.55, 0.2))
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6)
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(
        shader.ConnectableAPI(), "surface"
    )

    total = 0
    for bed in sorted(source_plants.GetChildren(), key=lambda prim: prim.GetName()):
        if not bed.GetName().startswith("Bed_"):
            continue
        bed_number = int(bed.GetName()[4:])
        output.OverridePrim(bed.GetPath())

        markers = sorted(
            [child for child in bed.GetChildren() if child.GetName().startswith("Plant_")],
            key=lambda prim: prim.GetName(),
        )
        positions = []
        for marker in markers:
            positions.append(
                tuple(UsdGeom.Xformable(marker).GetLocalTransformation().ExtractTranslation())
            )
            output.OverridePrim(marker.GetPath()).SetActive(False)

        instancer_path = bed.GetPath().AppendChild("PlantInstances")
        instancer = UsdGeom.PointInstancer.Define(output, instancer_path)
        prototype_path = instancer_path.AppendPath("Prototypes/PlantSprout")
        prototype = output.DefinePrim(prototype_path, "Mesh")
        prototype.GetReferences().AddReference(ASSET_PATH, "/Mesh")
        UsdShade.MaterialBindingAPI.Apply(prototype).Bind(material)

        count = len(positions)
        instancer.CreatePrototypesRel().SetTargets([prototype_path])
        instancer.CreateProtoIndicesAttr([0] * count)
        instancer.CreatePositionsAttr(positions)
        instancer.CreateIdsAttr(
            list(range(bed_number * 1000, bed_number * 1000 + count))
        )
        total += count
        print(f"Bed_{bed_number:02d}: replaced {count} markers")

    output.GetRootLayer().Save()
    print(f"Saved {total} point instances to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
