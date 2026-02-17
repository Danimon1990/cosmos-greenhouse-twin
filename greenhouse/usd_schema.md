# Greenhouse live state – USD schema

This document describes the prim hierarchy and attributes used in `greenhouse/live_state.usda`. The layer is a thin override layer that mirrors `greenhouse_state.json` for use in OpenUSD viewers or downstream composition.

## Layer

- **Path:** `greenhouse/live_state.usda`
- **Purpose:** Single layer containing only overrides (no geometry). Safe to overwrite by `usd_sync.py` each step.

## Prim hierarchy

```
/World
  /World/Greenhouse
    (attributes: timestamp)
    /World/Greenhouse/Environment
    /World/Greenhouse/Actuators
    /World/Greenhouse/Zones
      /World/Greenhouse/Zones/bed_1
      /World/Greenhouse/Zones/bed_2
      /World/Greenhouse/Zones/bed_3
```

## Attributes

### /World/Greenhouse

| Attribute   | Type   | Description                    |
|------------|--------|--------------------------------|
| timestamp  | string | UTC ISO timestamp of the step |

### /World/Greenhouse/Environment

| Attribute        | Type   | Description        |
|-----------------|--------|--------------------|
| temperature_c   | double | Air temperature °C |
| humidity_percent| double | Relative humidity %|
| co2_ppm         | double | CO₂ ppm            |
| light_lux        | double | Light level lux    |

### /World/Greenhouse/Actuators

| Attribute    | Type   | Description           |
|-------------|--------|-----------------------|
| fan         | double | Fan duty 0..1         |
| vent        | double | Vent opening 0..1    |
| water_valve | bool   | Water valve on/off    |

### /World/Greenhouse/Zones/bed_1, bed_2, bed_3

| Attribute       | Type   | Description              |
|-----------------|--------|--------------------------|
| crop           | string | Crop name (e.g. lettuce) |
| soil_moisture  | double | 0..1                     |
| plant_height_cm| double | Height cm                 |
| health         | string | Health label or score     |

## Mapping from JSON

- `greenhouse_state.json` → `live_state.usda`
- `timestamp` → `/World/Greenhouse.timestamp`
- `environment.*` → `/World/Greenhouse/Environment.*`
- `actuators.*` → `/World/Greenhouse/Actuators.*`
- `zones[0]` → `/World/Greenhouse/Zones/bed_1.*`
- `zones[1]` → `/World/Greenhouse/Zones/bed_2.*`
- `zones[2]` → `/World/Greenhouse/Zones/bed_3.*`

## Usage

- **Create/init:** `python -c "from usd_init import ensure_stage; ensure_stage('greenhouse/live_state.usda')"` or run `run_loop.py --steps 1 --usd`.
- **Sync:** `usd_sync.py` reads `greenhouse_state.json` and writes all values into `live_state.usda`. Idempotent; safe to run every step.
