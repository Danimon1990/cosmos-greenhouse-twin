# Greenhouse digital twin – data pipeline

Minimal prototype: state schema, simulated sensor drift, rule-based controller, and step logging.

## Structure

- **greenhouse_state.json** – Current state (environment, 3 zones, actuators). Edited by the loop.
- **simulate.py** – One-step simulation: drift temp/humidity, soil drying, apply watering if valve on.
- **brain.py** – Rule-based controller: sets fan, vent, water_valve from env and zone soil.
- **logger.py** – Appends each timestep (state after controller) as one JSON line to `history.jsonl`.
- **run_loop.py** – CLI: run N steps (simulate → brain → log), optional sleep and reset.

## Requirements

Python 3.10+. No external dependencies for the basic loop (stdlib only). For `--usd`, install OpenUSD: `pip install usd-core`.

## Run once (5 steps, default)

From the project root:

```bash
python greenhouse/run_loop.py --steps 5
```

## Run loop with options

```bash
python greenhouse/run_loop.py --steps 20 --sleep 1
python greenhouse/run_loop.py --steps 50 --state greenhouse/greenhouse_state.json --sleep 0.5
```

- **--steps** – Number of steps (default: 5).
- **--sleep** – Seconds to sleep between steps (default: 0).
- **--state** – Path to `greenhouse_state.json` (default: `greenhouse/greenhouse_state.json`).
- **--history** – Path to `history.jsonl` (default: `greenhouse/history.jsonl`).
- **--reset** – Restore initial state from template and exit.
- **--usd** – Sync state to `greenhouse/live_state.usda` each step (requires `pip install usd-core`).

## Reset state

Restore the initial greenhouse state (e.g. after a long run):

```bash
python greenhouse/run_loop.py --reset
```

## Where history is stored

Each timestep is appended as a single JSON line to:

- **greenhouse/history.jsonl** (default; override with `--history`).

The logged state is the state **after** the controller has set fan, vent, and water_valve for that step.

## USD sync (--usd)

With `--usd`, the loop creates or updates `greenhouse/live_state.usda` each step so a USD scene can reflect the same state. Prim layout and attributes are documented in **greenhouse/usd_schema.md**. Init (create stage/hierarchy) runs once; `usd_sync` runs after each step. Requires `pip install usd-core`.

## State schema

- **timestamp** – UTC ISO string.
- **environment** – temperature_c, humidity_percent, co2_ppm, light_lux.
- **zones** – List of 3 beds: crop, soil_moisture (0–1), plant_height_cm, health.
- **actuators** – fan (0–1), vent (0–1), water_valve (bool).
