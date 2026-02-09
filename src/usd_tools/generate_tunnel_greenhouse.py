#!/usr/bin/env python3
"""
Generate a tunnel-style (hoop house) greenhouse as a single UsdGeomMesh.
Semi-cylindrical arch extruded along X, with UsdShade material for translucent plastic.
Uses pxr (Usd, UsdGeom, UsdShade, Gf). Run from project root.
"""

import math
import os

try:
    from pxr import Gf, Usd, UsdGeom, UsdShade, Sdf
except ImportError:
    raise ImportError("pxr not found. Use a Python environment with USD (e.g. Omniverse).")

# --- Parameters (easy to change) ---
LENGTH = 18.0          # meters, along X (tunnel length; matches floor length when rotated into Z)
WIDTH = 12.0           # meters, span of tunnel (diameter of half-cylinder; matches floor width in X)
HEIGHT = 4.0           # meters, rise of arch
RADIAL_SEGMENTS = 24   # segments along the curved profile (smooth arch)
LENGTH_SEGMENTS = 18   # segments along X (length)

# Half-cylinder: span = WIDTH (Z from -R to R), arch rise = HEIGHT (Y from 0 to HEIGHT)
R = WIDTH / 2.0  # half-span for Z
HALF_LENGTH = LENGTH / 2.0


def _project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", ".."))


def _output_path():
    return os.path.join(_project_root(), "usd", "root", "greenhouse_tunnel.usda")


def build_tunnel_mesh(stage, mesh_path):
    """
    Build a half-cylinder tunnel mesh:
    - Profile in YZ: half circle from (Y=0, Z=-R) to (Y=0, Z=+R), arc above.
    - Extruded along X from -HALF_LENGTH to +HALF_LENGTH.
    - Vertices: (x, y, z) with (y,z) on the half-circle.
    """
    mesh = UsdGeom.Mesh.Define(stage, mesh_path)

    # Vertex grid: (length_segments+1) x (radial_segments+1)
    n_x = LENGTH_SEGMENTS + 1
    n_arc = RADIAL_SEGMENTS + 1
    points = []

    for ix in range(n_x):
        x = -HALF_LENGTH + ix * (LENGTH / LENGTH_SEGMENTS)
        for iarc in range(n_arc):
            # Angle 0 -> pi: Y = HEIGHT*sin(angle), Z = -R*cos(angle) => span 2R = WIDTH, rise = HEIGHT
            angle = iarc * (math.pi / RADIAL_SEGMENTS)
            y = HEIGHT * math.sin(angle)
            z = -R * math.cos(angle)
            points.append(Gf.Vec3f(x, y, z))

    mesh.CreatePointsAttr(points)

    # Triangle faces: quads between (ix, iarc) and (ix+1, iarc) and (ix+1, iarc+1) and (ix, iarc+1)
    face_vertex_counts = []
    face_vertex_indices = []

    for ix in range(LENGTH_SEGMENTS):
        for iarc in range(RADIAL_SEGMENTS):
            i00 = ix * n_arc + iarc
            i10 = (ix + 1) * n_arc + iarc
            i11 = (ix + 1) * n_arc + (iarc + 1)
            i01 = ix * n_arc + (iarc + 1)
            # Two triangles per quad; winding for outward-facing normals (right-hand rule)
            face_vertex_counts.extend([3, 3])
            face_vertex_indices.extend([i00, i10, i11, i00, i11, i01])

    mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
    mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

    # Extent: X [-HALF_LENGTH, HALF_LENGTH], Y [0, HEIGHT], Z [-R, R]
    extent_min = Gf.Vec3f(-HALF_LENGTH, 0.0, -R)
    extent_max = Gf.Vec3f(HALF_LENGTH, HEIGHT, R)
    mesh.CreateExtentAttr([extent_min, extent_max])

    return mesh


def create_plastic_material(stage, mesh_prim):
    """
    Create UsdShade material with Principled BSDF for thin translucent plastic:
    baseColor ~ (0.9, 0.9, 0.9), opacity ~ 0.5, roughness ~ 0.2.
    """
    mesh_path = mesh_prim.GetPath()
    mat_path = mesh_path.AppendChild("plastic_material")
    mat = UsdShade.Material.Define(stage, mat_path)

    shader_path = mat_path.AppendChild("PrincipledShader")
    shader = UsdShade.Shader.Define(stage, shader_path)
    shader.CreateIdAttr("UsdPreviewSurface")

    # Principled-like inputs: baseColor, opacity, roughness (thin translucent plastic)
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.9, 0.9, 0.9))
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.2)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    # Bind material to mesh (Apply expects UsdPrim, not schema)
    binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim.GetPrim())
    binding_api.Bind(mat)

    return mat


def main():
    out_path = _output_path()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    stage.SetMetadata("metersPerUnit", 1)
    stage.SetMetadata("upAxis", "Y")
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))
    world = stage.GetDefaultPrim()

    mesh_path = world.GetPath().AppendChild("TunnelCover")
    mesh_prim = build_tunnel_mesh(stage, mesh_path)

    create_plastic_material(stage, mesh_prim)

    stage.Save()
    print(f"Saved: {out_path}")
    print(f"  Length={LENGTH}m, Width={WIDTH}m, Height={HEIGHT}m")
    print(f"  Radial segments={RADIAL_SEGMENTS}, length segments={LENGTH_SEGMENTS}")


if __name__ == "__main__":
    main()
