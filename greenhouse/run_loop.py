#!/usr/bin/env python3
"""
CLI runner: execute N simulation steps (simulate -> brain -> log).

Usage:
  python greenhouse/run_loop.py --steps 5
  python greenhouse/run_loop.py --steps 20 --sleep 1 --state greenhouse/greenhouse_state.json
  python greenhouse/run_loop.py --reset
"""

import argparse
import json
import sys
import time
from pathlib import Path

from brain import step as brain_step
from logger import log_step
from simulate import load_state, save_state, step as simulate_step

# Default state path relative to this file
GREENHOUSE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = GREENHOUSE_DIR / "greenhouse_state.json"
DEFAULT_HISTORY_PATH = GREENHOUSE_DIR / "history.jsonl"
DEFAULT_USD_PATH = GREENHOUSE_DIR / "live_state.usda"

INITIAL_STATE = {
    "timestamp": "2026-02-14T12:00:00.000000Z",
    "environment": {
        "temperature_c": 22.0,
        "humidity_percent": 55.0,
        "co2_ppm": 420.0,
        "light_lux": 8000.0,
    },
    "zones": [
        {"crop": "lettuce", "soil_moisture": 0.5, "plant_height_cm": 12.0, "health": 0.9},
        {"crop": "lettuce", "soil_moisture": 0.45, "plant_height_cm": 10.0, "health": 0.85},
        {"crop": "lettuce", "soil_moisture": 0.55, "plant_height_cm": 14.0, "health": 0.92},
    ],
    "actuators": {
        "fan": 0.0,
        "vent": 0.0,
        "water_valve": False,
    },
}


def reset_state(state_path: Path) -> None:
    """Restore initial greenhouse state to state_path."""
    with open(state_path, "w") as f:
        json.dump(INITIAL_STATE, f, indent=2)
        f.write("\n")
    print(f"Reset state to {state_path}")


def run_loop(
    state_path: Path,
    history_path: Path,
    steps: int,
    sleep_sec: float,
    usd_path: Path | None = None,
) -> None:
    """Run steps: load -> simulate -> brain -> log [-> usd_sync if usd_path]; print status each step."""
    if usd_path is not None:
        from usd_init import ensure_stage
        ensure_stage(usd_path)

    state = load_state(state_path)
    for i in range(steps):
        simulate_step(state, state_path=None)
        brain_step(state)
        save_state(state_path, state)
        log_step(history_path, state)

        if usd_path is not None:
            from usd_sync import sync
            sync(state_path=state_path, usd_path=usd_path)
            print(f"  usd updated: {usd_path}")

        env = state["environment"]
        act = state["actuators"]
        ts = state["timestamp"]
        print(
            f"step {i+1}/{steps}  {ts}  "
            f"temp={env['temperature_c']:.1f}C  humidity={env['humidity_percent']:.0f}%  "
            f"fan={act['fan']:.2f}  vent={act['vent']:.2f}  water_valve={act['water_valve']}"
        )
        if i < steps - 1 and sleep_sec > 0:
            time.sleep(sleep_sec)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run greenhouse simulation loop")
    parser.add_argument("--steps", type=int, default=5, help="Number of steps to run")
    parser.add_argument("--sleep", type=float, default=0, help="Seconds to sleep between steps")
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to greenhouse_state.json",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=DEFAULT_HISTORY_PATH,
        help="Path to history.jsonl",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Restore initial state from template and exit",
    )
    parser.add_argument(
        "--usd",
        action="store_true",
        help="Sync state to greenhouse/live_state.usda each step",
    )
    args = parser.parse_args()

    state_path = Path(args.state).resolve()

    history_path = args.history
    if not history_path.is_absolute():
        history_path = GREENHOUSE_DIR / history_path.name
    history_path = history_path.resolve()

    if args.reset:
        reset_state(state_path)
        return 0

    if not state_path.exists():
        print(f"Error: State file not found: {state_path}", file=sys.stderr)
        return 1

    usd_path = DEFAULT_USD_PATH.resolve() if args.usd else None

    try:
        run_loop(state_path, history_path, args.steps, args.sleep, usd_path=usd_path)
    except (IOError, json.JSONDecodeError, KeyError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
