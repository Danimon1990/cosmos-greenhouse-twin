# Professional OpenUSD Architecture Plan

Status: phase 1 scene shell implemented  
Source reviewed: `usd/source/blender/greenhouse_exchange.usdc`  
Working rule: preserve the Blender source and raw USDC export until the composed replacement passes validation.

## 1. Current-state audit

The Blender export is a useful source layer, but it should not become the production root stage.

| Item | Current result | Architectural consequence |
|---|---:|---|
| Stage units | meters | Keep unchanged across every asset and scenario. |
| Up axis | Y | Keep unchanged across every asset and scenario. |
| Default prim | `World` | Valid for the exchange stage; reusable assets need their own stable default prims. |
| Sublayers | none | All authored concerns are currently inseparable. |
| Prims | 2,207 | The scene needs asset and functional boundaries. |
| Meshes | 1,023 | Repeated content should be measured and converted to instances where appropriate. |
| Materials / shaders | 45 / 45 | Move asset-local looks with their assets; reserve scene looks for shared overrides. |
| Instances | 0 | Plants and repeated structural/irrigation parts are optimization candidates. |
| Model kinds | 4 component opinions | Assemblies, components, and groups need deliberate model hierarchy. |
| External dependencies | one remote conveyor material | Vendor or localize it so the scene is reproducible offline. |

The export already contains a strong semantic starting hierarchy under
`/World/Environment/Greenhouse`: `Structure`, `Devices`, `GrowingAreas`,
`Plants`, `Navigation`, `Doors`, `Irrigation`, `Ventilation`, and `Utilities`.
These stable functional names should be preserved.

Content that should not remain mixed into the production asset includes the
Blender/Kit viewport cameras, `/Render`, `/PhysicsScene`, top-level
`/env_light`, loose lights and cameras, and materials under `/_materials`.

## 2. Target composition

Open `usd/scenes/greenhouse_main.usda` as the normal production entry point.
It should contain composition and placements only—no generated mesh data and
no accidental session edits.

```text
usd/
├── source/
│   └── blender/
│       └── greenhouse_exchange.usdc       # immutable source snapshot
├── assets/
│   ├── greenhouse/
│   │   ├── greenhouse.usda                # asset interface + variants
│   │   ├── greenhouse_structure.usdc      # heavy render geometry payload
│   │   ├── greenhouse_systems.usda        # system asset references
│   │   ├── greenhouse_collision.usda      # collision representation
│   │   ├── greenhouse_semantics.usda      # labels and robot-relevant metadata
│   │   └── looks/
│   │       ├── greenhouse_materials.usda
│   │       └── greenhouse_bindings.usda
│   ├── plants/
│   │   └── <species>/
│   │       ├── <species>.usda             # stable asset interface
│   │       ├── <species>_geom.usdc
│   │       └── <species>_looks.usda
│   ├── devices/
│   │   ├── fan/
│   │   ├── valve/
│   │   ├── vent/
│   │   └── sensor/
│   ├── utility_station/
│   ├── robot_access/
│   └── props/
│       ├── shovel/
│       └── wheelbarrow/
├── layouts/
│   ├── greenhouse_layout.usda             # asset placement and bed layout
│   ├── plant_distribution.usda            # point instancers by bed/zone
│   └── navigation.usda                    # paths, docks, restricted zones
├── config/
│   ├── physics.usda                       # authored physics configuration
│   ├── semantics.usda                     # scene-level semantic overrides
│   └── sensors.usda                       # sensor configuration and mounts
├── runtime/
│   └── live_state.usda                    # only canonical generated state
├── shots/
│   ├── daylight.usda                      # cameras, lights, render settings
│   └── demo_dry_zone.usda                 # shot/scenario override
└── scenes/
    ├── greenhouse_main.usda               # production assembly
    ├── greenhouse_sim.usda                # simulation configuration
    └── greenhouse_demo.usda               # presentation entry point
```

Binary `.usdc` is appropriate for generated heavy geometry. Human-authored
interfaces, assemblies, configuration, variants, and overrides should remain
`.usda` for reviewability. Flattened files, if needed, belong in a generated
delivery folder and are never the source of truth.

## 3. Stable scene namespace

```text
/World                              (kind=assembly, defaultPrim)
├── Environment                    (kind=group)
│   ├── Greenhouse                 (referenced model, kind=assembly)
│   │   ├── Structure
│   │   ├── GrowingAreas
│   │   ├── Navigation
│   │   ├── Irrigation
│   │   ├── Ventilation
│   │   ├── Doors
│   │   └── Utilities
│   └── Exterior
├── Robots
├── Sensors
├── Cameras
├── Lights
├── Looks
└── Simulation
    ├── Zones
    ├── Devices
    └── State
```

Keep object identity paths stable while geometry below an asset changes.
Names use `UpperCamelCase` for prims and `lower_snake_case` for files. Avoid
Blender collision suffixes as identity; replace names such as `Cylinder` or
number-only suffixes with functional names before publishing an asset.

Robot access routes, docking poses, restricted zones, tool attachment frames,
door clearances, sensor mounts, and irrigation control zones are first-class
authored prims. They must not be inferred later from render meshes.

## 4. Composition rules

- **References:** independently addressable assets such as the greenhouse,
  utility station, fans, valves, sensors, props, and robots.
- **Payloads:** heavy render geometry and large plant distributions that should
  load on demand.
- **Sublayers:** orthogonal opinions over one namespace, such as configuration,
  semantics, live state, and shot overrides. Do not use sublayers as a substitute
  for asset encapsulation.
- **Variants:** discrete authored choices only: `lod`, `representation`, plant
  `species`, `growthStage`, and `healthState`. Do not encode continuous telemetry
  as variants.
- **Inherits/specializes:** introduce only after a repeated, stable asset contract
  is demonstrated; they are not required for the first migration.

Every reusable asset must provide:

- a single stable `defaultPrim`;
- `kind=component` at its model root, or `kind=assembly` when it contains models;
- meters and Y-up metadata;
- local geometry and local material scope;
- documented attachment/control interface paths;
- no scene cameras, lights, render products, or runtime state.

## 5. Plants and repeated content

Split plant distributions by bed and operational zone, matching the existing
24-zone reasoning model where that model remains authoritative. Use one
`UsdGeomPointInstancer` per independently controlled bed/zone when plants only
need visual variation and shared collision behavior.

Plant prototype assets should expose meaningful variants such as species,
growth stage, health state, and LOD. Use `protoIndices`, transforms, scales, and
primvars for per-plant variation. Promote a plant to an ordinary referenced prim
only when it needs unique selection, articulation, lifecycle, or rigid-body
interaction.

Measure repeated roof arches, supports, clamps, sprinklers, and fan parts for
instanceability. Instance only identical topology/material packages with no
required per-instance descendant overrides.

## 6. Runtime and scenario ownership

`usd/runtime/live_state.usda` is the only canonical generated state layer. It
contains overrides and telemetry, never geometry. Existing competing live-state
files under `greenhouse/` and `usd/layers/` must be reconciled during migration;
writers should target one path only.

Recommended strength from weak to strong:

```text
asset defaults
  < layout and authored configuration
  < physics / semantics / sensor configuration
  < runtime/live_state.usda
  < shot or scenario override
  < session layer (temporary user edits only)
```

Animations and actuator state need one owner per property. Authored motion clips
belong with the asset or scenario; live telemetry belongs only in live state.

## 7. Migration sequence

### Phase 0 — Freeze and baseline

1. Keep `Greenhouse_scene.blend` and `greenhouse_exchange.usdc` unchanged.
2. Record the raw stage metadata, hierarchy, bounds, prim/type counts, materials,
   dependencies, and reference renders.
3. Decide whether the legacy procedural greenhouse remains a demo product or is
   retired after visual and behavior parity.

### Phase 1 — Publish the scene shell

1. Create the new `scenes`, `layouts`, `config`, `runtime`, and `shots` roots.
2. Author the stable `/World` hierarchy and model kinds.
3. Move camera, lighting, and render settings into a daylight shot layer.
4. Exclude Blender/Kit viewport prims and the exchange-stage physics scene.

### Phase 2 — Extract reusable assets

1. Extract the greenhouse structure and functional systems without renaming their
   published interface paths.
2. Publish utility station, robot-access assembly, shovel, wheelbarrow, fans,
   valves, vents, and sensors as referenced assets where reuse or independent
   simulation justifies it.
3. Relocate materials to asset-local `Looks` scopes and author a scene-level looks
   layer only for deliberate shared overrides.
4. Vendor or replace the remote conveyor material dependency.

### Phase 3 — Optimize repetition

1. Convert plants into prototypes plus per-zone point instancers.
2. Evaluate repeated structural and irrigation parts for native instances.
3. Add LOD or representation variants only after visual parity is established.

### Phase 4 — Add simulation interfaces

1. Author collision, rigid bodies, joints, articulations, sensors, and semantic
   labels in dedicated layers after the visual composition is stable.
2. Author navigation paths, clearances, docks, restricted zones, mounts, and tool
   frames explicitly.
3. Connect all state writers to the single runtime layer.

### Phase 5 — Cut over safely

1. Validate the unloaded and fully loaded stages.
2. Compare bounds and reference renders to the raw export.
3. Exercise live telemetry and scenario overrides.
4. Update application entry points only after parity passes.
5. Archive, but do not delete, the legacy scene until downstream users confirm the
   new entry points.

## 8. Acceptance gates

The migration is complete when:

- every composed stage opens with no unresolved assets or invalid prim paths;
- the root scene contains no mesh specs and stays small;
- each reusable asset has a valid default prim and model kind;
- all stages agree on meters and Y-up;
- the normal scene opens without loading heavy payloads;
- materials resolve without network access;
- no Blender/Kit editor artifacts appear in production namespaces;
- repeated plants are controlled by bed/zone without duplicating prototype mesh;
- there is exactly one writable live-state layer and no duplicate state authority;
- collision, semantics, cameras, lights, and render settings can be overridden
  independently where the workflow requires it;
- a visual comparison and robot-readiness review both pass before source assets
  are retired.

## 9. Immediate implementation slice

The first safe implementation milestone should create only the scene shell,
greenhouse asset interface, daylight shot, and canonical live-state location.
Reference or payload the unchanged exchange content temporarily behind the new
interface. This proves namespaces and composition strength before destructive
mesh extraction or path migration begins.

After that milestone, extract one bounded vertical slice—preferably a fan or
valve asset—through geometry, looks, semantics, physics interface, and runtime
state. Use the lessons from that asset to standardize the rest of the conversion.

## 10. Implemented phase 1 entry points

The first recoverable composition slice is now available:

- `usd/scenes/greenhouse_main.usda` is the production assembly.
- `usd/scenes/greenhouse_animation_preview.usda` is a 240-frame preview of the
  sliding front door, three fan rotors, and nine visual sprinkler streams.
- `usd/runtime/live_state.usda` is the canonical Cosmos/runtime write target.
- `usd/layouts/robots.usda` owns robot placement and reserves spawn, dock, and
  restricted-area interfaces independently from greenhouse geometry.
- `usd/config/animation.usda` owns actuator interfaces and pivot-level transform
  ops; it deliberately contains no scenario time samples.
- `usd/shots/animation_preview.usda` owns deterministic presentation animation.

Layer strength in `greenhouse_main.usda` is authored strongest to weakest:

```text
runtime state
daylight shot
exchange cleanup
animation interfaces
simulation configuration
robot layout
greenhouse asset interface
raw Blender exchange
```

This means Cosmos can override authored command defaults without editing the
source export. The animation preview is a stronger wrapper around the main stage,
so its time samples win only when that preview entry point is opened.

The current water representation is intentionally a visual `BasisCurves` effect,
not fluid simulation. Irrigation command state, visible spray, future soil
response, and future rendered wetness remain independent signals.
