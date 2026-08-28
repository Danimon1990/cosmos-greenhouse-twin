---
name: openusd-greenhouse-architecture
description: Design, review, or refactor the OpenUSD composition architecture for this robot-assisted greenhouse, including assets, model hierarchy, references, payloads, variants, point instancers, layers, naming, and runtime state. Use for USD scene organization and asset-boundary decisions; do not use for PhysX tuning or Blender modeling alone.
---

# OpenUSD Greenhouse Architecture

Treat Blender files as authoring sources and USD as the composed simulation and delivery representation. Preserve source files until their USD replacements are validated.

## Project invariants

- Use meters and a documented up axis consistently across every asset and stage.
- Keep the root scenario layer small. It should compose assets and scenario layers, not contain generated meshes or accidental session edits.
- Give reusable assets a stable `defaultPrim`, model `kind`, local materials, and a predictable interface.
- Use references for independently addressable assets and payloads for heavy content that should load on demand.
- Separate authored configuration from generated runtime telemetry. There must be one canonical live-state layer.
- Keep render geometry, collision geometry, physics opinions, semantics, animation, cameras, and lighting independently overrideable when that separation serves a real workflow.
- Never flatten the working composition as the source of truth. Flatten only intentional delivery artifacts.

## Greenhouse organization

Prefer stable functional groups beneath `/World`: `Environment`, `Robots`, `Sensors`, `Cameras`, `Lights`, `Looks`, and `Simulation`. Within the greenhouse, preserve addressable systems such as `Structure`, `GrowingAreas`, `Navigation`, `Irrigation`, `Ventilation`, `Doors`, and `Utilities`.

Robot-relevant paths, restricted zones, docking frames, sensor mounts, and tool attachment frames are first-class authored data, not visual decoration.

## Plants

- Represent repeated plants with `UsdGeomPointInstancer` when individual rigid-body interaction is not required.
- Build reusable prototype assets by species and meaningful state family.
- Use prototype variants for discrete authored choices such as species, growth stage, health state, or LOD.
- Use `protoIndices`, transforms, scales, and primvars for per-instance distribution and variation.
- Split instancers by bed or management zone when telemetry, visibility, harvesting, or state changes need independent control.
- Promote a plant to an ordinary referenced prim only when it requires unique articulation, physics, selection, or lifecycle behavior.

## Review workflow

Before changing composition, inspect the layer stack, prim hierarchy, default prims, model kinds, asset dependencies, and existing user edits. Propose migrations that keep the current stage recoverable. Validate composed stages for unresolved assets, invalid prim paths, duplicate state authorities, and unintended opinions in root layers.
