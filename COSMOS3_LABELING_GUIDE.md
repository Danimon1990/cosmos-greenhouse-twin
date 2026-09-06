# Cosmos 3 and Isaac Sim Labeling Guide

## What the labels are for

Cosmos 3 Reasoner can analyze an ordinary RGB image without semantic labels. In this project, USD semantic labels are useful for Isaac Sim semantic segmentation, bounding boxes, synthetic-data generation, and reliably matching visible objects to greenhouse telemetry.

Use the newer `SemanticsLabelsAPI` supported by the installed Isaac Sim version.

## Recommended greenhouse taxonomy

Keep `class` labels simple and visually meaningful:

| Object | Class label |
| --- | --- |
| Greenhouse structure | `greenhouse_structure` |
| Soil-bed geometry | `soil_bed` |
| Spinach or sprout prototype | `plant` |
| Drip hoses | `irrigation_hose` |
| Inspection gantry | `inspection_gantry` |
| MUVI robot | `mobile_robot` |
| Cameras | `sensor_camera` |
| Fans | `ventilation_fan` |
| Valves | `irrigation_valve` |
| Floor or path | `walkway` |

Use additional label types for identity and state:

- `species`: `spinach`
- `growth_stage`: `sprout`
- `zone`: `bed_01`, `bed_02`, and so on
- `device_id`: the matching ID from `config/greenhouse.registry.json`

Do not use `bed_01`, `bed_02`, and similar values as classes. Every bed should have class `soil_bed`; the specific bed identity belongs in its `zone` label.

## Labeling through Isaac Sim

1. Create an editable layer named `usd/config/semantics.usda`.
2. Make that layer the current authoring layer.
3. Open the **Semantics Schema Editor** extension.
4. Select a meaningful parent prim, such as `Bed_01`.
5. Add semantic type `class` with label `soil_bed`.
6. Add semantic type `zone` with label `bed_01`.
7. Repeat for the other beds and major greenhouse systems.
8. Save the semantics layer. Do not write labels into the imported Blender exchange layer.

The installed editor can upgrade old `SemanticsAPI` entries to the newer `SemanticsLabelsAPI` representation.

## Exact USD examples

A soil bed should look like this:

```usda
over Xform "Bed_01" (
    prepend apiSchemas = [
        "SemanticsLabelsAPI:class",
        "SemanticsLabelsAPI:zone"
    ]
)
{
    token[] semantics:labels:class = ["soil_bed"]
    token[] semantics:labels:zone = ["bed_01"]
}
```

Label the shared plant prototype instead of labeling hundreds of instances:

```usda
over "PlantSprout" (
    prepend apiSchemas = [
        "SemanticsLabelsAPI:class",
        "SemanticsLabelsAPI:species",
        "SemanticsLabelsAPI:growth_stage"
    ]
)
{
    token[] semantics:labels:class = ["plant"]
    token[] semantics:labels:species = ["spinach"]
    token[] semantics:labels:growth_stage = ["sprout"]
}
```

## Testing semantic segmentation

Attach a semantic-segmentation annotator to the actual composed scan-camera path:

```python
import omni.replicator.core as rep

render_product = rep.create.render_product(
    "/World/Sensors/PlantInspectionGantry/Horizontal_Mount/Cam_mount/PlantScanCamera",
    (1280, 720),
)

semantic = rep.AnnotatorRegistry.get_annotator(
    "semantic_segmentation",
    init_params={"semanticTypes": ["class"]},
)
semantic.attach(render_product)
```

The result should include a colored segmentation image and a mapping from pixel IDs or colors to labels such as `plant`, `soil_bed`, and `irrigation_hose`.

## Context to send to Cosmos 3

Send the natural RGB frame together with structured bed and telemetry context:

```json
{
  "camera": "PlantScanCamera",
  "visibleBeds": ["bed_04", "bed_05"],
  "classes": ["plant", "soil_bed", "irrigation_hose"],
  "zones": {
    "bed_04": {"soilMoisturePct": 22},
    "bed_05": {"soilMoisturePct": 47}
  }
}
```

This is more useful than sending segmentation alone: Cosmos sees the natural greenhouse image while the structured context provides stable bed identities and sensor readings.
