#!/usr/bin/env python3
"""Validate versioned greenhouse contracts, examples, and registry references."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "v1"
EXAMPLES = ROOT / "contracts" / "examples"
REGISTRY_PATH = ROOT / "config" / "greenhouse.registry.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate(instance_path: Path, schema_path: Path) -> None:
    validator = Draft202012Validator(
        load_json(schema_path), format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(load_json(instance_path)), key=lambda e: list(e.path))
    if errors:
        details = "\n".join(
            f"  {instance_path.relative_to(ROOT)}:{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(details)


def validate_registry_references() -> None:
    registry = load_json(REGISTRY_PATH)
    zones = {zone["zoneId"] for zone in registry["zones"]}
    devices = {device["deviceId"]: device for device in registry["devices"]}

    all_ids = [zone["zoneId"] for zone in registry["zones"]] + list(devices)
    duplicates = sorted({item for item in all_ids if all_ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"Duplicate registry IDs: {', '.join(duplicates)}")

    for zone in registry["zones"]:
        parent = zone.get("parentZoneId")
        if parent and parent not in zones:
            raise ValueError(f"Unknown parent zone {parent!r} for {zone['zoneId']!r}")

    for device in registry["devices"]:
        if device["zoneId"] not in zones:
            raise ValueError(f"Unknown zone for {device['deviceId']!r}")
        unknown_observed = set(device.get("observedZoneIds", [])) - zones
        if unknown_observed:
            raise ValueError(
                f"Unknown observed zones for {device['deviceId']!r}: {sorted(unknown_observed)}"
            )

    telemetry = load_json(EXAMPLES / "telemetry-event.json")
    telemetry_device = devices.get(telemetry["deviceId"])
    if not telemetry_device or telemetry_device["zoneId"] != telemetry["zoneId"]:
        raise ValueError("Telemetry example device/zone does not match the registry")

    targets = [load_json(EXAMPLES / "command.json")["targetId"]]
    targets.extend(
        action["targetId"]
        for action in load_json(EXAMPLES / "cosmos-decision.json")["proposedActions"]
        if action["actionType"] not in {"raise-alert", "request-inspection", "no-action"}
    )
    unknown_targets = sorted(set(targets) - devices.keys())
    if unknown_targets:
        raise ValueError(f"Unknown example command targets: {', '.join(unknown_targets)}")


def main() -> None:
    pairs = (
        (REGISTRY_PATH, CONTRACTS / "device-registry.schema.json"),
        (EXAMPLES / "telemetry-event.json", CONTRACTS / "telemetry-event.schema.json"),
        (EXAMPLES / "command.json", CONTRACTS / "command.schema.json"),
        (EXAMPLES / "cosmos-decision.json", CONTRACTS / "cosmos-decision.schema.json"),
    )
    for instance_path, schema_path in pairs:
        validate(instance_path, schema_path)
        print(f"valid: {instance_path.relative_to(ROOT)}")
    validate_registry_references()
    print("valid: registry references and example targets")


if __name__ == "__main__":
    main()
