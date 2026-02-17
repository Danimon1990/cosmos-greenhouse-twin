"""
Append each timestep state as one JSON line to history.jsonl.
"""

import json
from pathlib import Path


def log_step(history_path: Path, state: dict) -> None:
    """
    Append state (after controller) as a single JSON line to history_path.
    """
    with open(history_path, "a") as f:
        f.write(json.dumps(state) + "\n")
