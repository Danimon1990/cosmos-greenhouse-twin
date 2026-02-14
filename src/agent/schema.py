"""
Schema types for Cosmos agent context and response.

Used by cosmos_agent.py and cosmos_client.py for consistent JSON shapes.
"""

from typing import Any, Literal, TypedDict


class SensorSnapshot(TypedDict):
    temperatureC: float
    humidityPct: float
    soilMoisturePct: float


class DeviceSnapshot(TypedDict):
    fanPower: float
    ventPosition: float
    valveFlow: float


class ContextPayload(TypedDict):
    sensors: SensorSnapshot
    devices: DeviceSnapshot


ActionType = Literal["set_fan", "set_vent", "set_valve", "send_alert", "no_action"]


class Recommendation(TypedDict, total=False):
    action: ActionType
    value: float | None
    why: str
    confidence: float


class CosmosResponsePayload(TypedDict, total=False):
    explanation: str
    recommendations: list[Recommendation]


def parse_response(raw: dict[str, Any]) -> CosmosResponsePayload:
    """Extract explanation and recommendations from raw API response."""
    out: CosmosResponsePayload = {}
    if "explanation" in raw and isinstance(raw["explanation"], str):
        out["explanation"] = raw["explanation"]
    if "recommendations" in raw and isinstance(raw["recommendations"], list):
        out["recommendations"] = []
        for r in raw["recommendations"]:
            if isinstance(r, dict):
                rec: Recommendation = {}
                if r.get("action") in ("set_fan", "set_vent", "set_valve", "send_alert", "no_action"):
                    rec["action"] = r["action"]
                if "value" in r:
                    rec["value"] = r["value"] if r["value"] is not None else None
                if isinstance(r.get("why"), str):
                    rec["why"] = r["why"]
                if isinstance(r.get("confidence"), (int, float)):
                    rec["confidence"] = float(r["confidence"])
                out["recommendations"].append(rec)
    return out
