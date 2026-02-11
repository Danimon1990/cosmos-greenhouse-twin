# cosmos-greenhouse-twin

Minimal OpenUSD greenhouse digital twin skeleton for an NVIDIA Cosmos Reason 2 hackathon submission.

## Project overview

This repo provides a **minimal OpenUSD greenhouse digital twin** with:

- **Structure**: floor + tunnel-style plastic cover (semi-cylindrical hoop house from `greenhouse_tunnel.usda`), 12×18 m footprint, 4 m arch height
- **Devices**: fan, vent, valve, sensor (Xforms with attributes)
- **Plants**: 8 beds, 7 walkways, plant instances (`plant_sprout_abstract.usda`) per bed; **plantHealth** variant set (healthy / stressed)
- **Looks**: UsdPreviewSurface materials (SoilMat, PlantMat, PathMat, PlasticMat) in `greenhouse_looks.usda`, sublayered into the root

Human-readable `.usda`; loads in USD Composer / usdview / Isaac Sim. Meters, Y-up.

## Greenhouse dimensions and layout

- **Footprint**: 12 m wide (X) × 18 m long (Z); greenhouse centered at origin; Y-up.
- **Floor**: Spans X ∈ [-6, +6], Z ∈ [-9, +9].
- **Side clearance**: 1 m free space along each long wall (usable width band X ∈ [-5, +5]).
- **Entrances**: 1 m free at each end along Z (beds span 16 m, centered at Z = 0).
- **Beds**: 8 beds, each 0.8 m wide (X) × 16 m long (Z) × 0.4 m high, with 0.05 m inner margin on each side of the usable band.
- **Walking paths**: 7 paths between the 8 beds, each 0.5 m wide × 16 m long; total path width 3.5 m; beds + paths fit in the 10 m usable width with 0.1 m slack (0.05 m margin per side).

## Folder structure

```
cosmos-greenhouse-twin/
  README.md
  .gitignore

  usd/
    root/
      greenhouse.usda          # Root assembly (open this in Composer)
      greenhouse_tunnel.usda   # Tunnel mesh + plastic material (generated)
      greenhouse_looks.usda    # Materials (SoilMat, PlantMat, PathMat, PlasticMat)
    components/
      structure.usda           # Floor + TunnelCover reference
      devices.usda             # Fan, vent, valve, sensor (static defs)
      plants.usda              # 8 beds, 7 walkways, plant instances
    layers/
      live_state.usda          # Live telemetry + actuator overrides (strongest)
    variants/
      plant_states.usda        # plantHealth variant definitions
    assets/
      plant_sprout/            # Plant mesh asset (referenced by plants.usda)

  src/
    usd_tools/
      inspect_stage.py              # Print layer stack, prim tree, device/sensor values, variant
      generate_tunnel_greenhouse.py # Generate tunnel mesh (18×12×4 m)
      assign_greenhouse_materials.py # Create materials and bindings
```

## Digital Twin Layering

The scene is split into layers so that **static geometry** stays in components and **dynamic state** can be updated without touching the base assets:

- **`components/*.usda`** — Static geometry and structure. `structure.usda` (floor, tunnel), `devices.usda` (device prims, types, transforms), `plants.usda` (beds, walkways, plant instances). These files **define** prims and fixed attributes.

- **`variants/*.usda`** — Scenario or health variants (e.g. `plant_states.usda` with `plantHealth`: healthy / stressed). Composed as a **sublayer** so variant selections and overrides apply over the root.

- **`layers/live_state.usda`** — **Live telemetry and actuator overrides only** (`over` prims, no new geometry). It authors dynamic attributes on existing device/sensor prims: `device:power`, `device:position`, `device:flow`, `sensor:temperatureC`, `sensor:humidityPct`, `sensor:soilMoisturePct`, `state:tick`, etc. This file is the **strongest** sublayer so its values win at runtime.

- **`root/greenhouse.usda`** — Root stage. Composes everything via **sublayers** (plant_states → greenhouse_looks → live_state), **references** (structure, devices), and **payload** (plants). Open this file in Composer to view the full digital twin.

**Sublayer order (strength):** In USD, sublayers are ordered from **weakest to strongest**. The **last** sublayer wins when the same attribute is authored in multiple layers. So `live_state.usda` is listed **last** in `greenhouse.usda`’s `sublayers`; any value it sets for a device or sensor overrides the same attribute from components or variants.

**Editing live state:** To simulate new telemetry or actuator values, edit `usd/layers/live_state.usda` (e.g. change `sensor:temperatureC`, `device:power`, or `state:tick`). Save and reload the stage in Composer (or run `inspect_stage.py`) to see the updated composed values. No need to edit `devices.usda` for live data.

## How to open greenhouse.usda in USD Composer

1. Install [NVIDIA Omniverse](https://developer.nvidia.com/omniverse) and **USD Composer** (or **Isaac Sim** with Composer).
2. In Composer: **File → Open** (or drag-and-drop).
3. Open: `usd/root/greenhouse.usda` (use the full path or navigate from the project root).
4. The stage will load with `World` as the default prim; structure, devices, and plants appear under `World/Environment/Greenhouse`.

Paths in the root stage are relative to `usd/root/`, so `../components/structure.usda` etc. resolve correctly when opening from that directory.

## How to run inspect_stage.py

From the project root:

```bash
# Optional: use a venv with pxr (e.g. Omniverse Python or USD Python bindings)
python src/usd_tools/inspect_stage.py
```

The script resolves `usd/root/greenhouse.usda` relative to the project root, loads it with `pxr.Usd`, prints the prim tree, and prints sensor/device attributes (e.g. sensor temperature, humidity, soil moisture).

Requires **USD Python bindings** (`pxr.Usd`). If you use Omniverse, its Python environment usually includes these.

### Other scripts (run from project root, with pxr available)

- **Tunnel generator** (creates/overwrites `usd/root/greenhouse_tunnel.usda`):
  ```bash
  python src/usd_tools/generate_tunnel_greenhouse.py
  ```
- **Materials / looks** (creates/overwrites `usd/root/greenhouse_looks.usda`; root already sublayers it):
  ```bash
  python src/usd_tools/assign_greenhouse_materials.py
  ```

## Composition arcs used

- **References** (in `greenhouse.usda`):  
  `structure.usda` and `devices.usda` are **referenced** into the root. They load with the stage and define the greenhouse structure and devices.

- **Payload** (in `greenhouse.usda`):  
  `plants.usda` is attached as a **payload**. It can be loaded/unloaded in Composer (e.g. “Load Payloads” / “Unload Payloads”) to show or hide plant geometry without changing the root structure.

- **Variants** (in `greenhouse.usda` and `plant_states.usda`):  
  The root defines a **variant set** `plantHealth` with values `healthy` and `stressed`. Variant opinions (e.g. overrides for plant appearance) can live in the root or in a separate file like `variants/plant_states.usda` that is applied via the variant set. Here, the variant set is on the root and the actual variant content (e.g. green vs stressed look) is intended to be authored in the variant blocks or in referenced payload/variant assets.

No physics or Cosmos-specific logic is included; this is a minimal skeleton for extension.

## Troubleshooting: plants not visible

- **Payload vs reference**: The **Plants** prim (beds + walkways + plants) is loaded via a **payload** (`plants.usda`). The plants themselves are **references** to `usd/assets/plant_sprout/plant_sprout_abstract.usda` inside that payload. So if you see beds but not plants, the payload is loaded; the issue is usually the plant **reference** path or how instances are drawn.

- **What to try**
  1. **Open the stage from the project root** so relative paths resolve correctly:
     ```bash
     cd /path/to/cosmos-greenhouse-twin
     usdview usd/root/greenhouse.usda
     ```
  2. **Ensure the Plants payload is loaded** (e.g. in usdview: select the Plants prim and load payloads if there is an unload indicator).
  3. **Open the plant asset alone** to confirm it displays:
     ```bash
     usdview usd/assets/plant_sprout/plant_sprout_abstract.usda
     ```
  4. **Instancing**: Plant prims use `instanceable = false` so they always expand; some viewers do not draw instanceable masters by default.
  5. **Path resolution**: References in `plants.usda` use `@../assets/plant_sprout/plant_sprout_abstract.usda@` (relative to `usd/components/`). Resolvers typically anchor this to the layer file; if your app resolves relative to the current working directory, run it from the project root.
