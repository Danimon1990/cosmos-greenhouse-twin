"""
Cosmos Reason 2 HTTP client for the greenhouse digital twin.

If COSMOS_API_URL or COSMOS_API_KEY is missing, returns a mocked response
based on sensor values (e.g. humidity > 80 → recommend fan 0.4).
Otherwise POSTs to the configured endpoint with model, messages, and image.

Request payload is built in one function so the endpoint format can be
adjusted easily.
"""

import base64
import json
import os
from typing import Any

from schema import ContextPayload, CosmosResponsePayload, parse_response

# Environment variables (no secrets in code)
COSMOS_API_URL = os.environ.get("COSMOS_API_URL", "").strip()
COSMOS_API_KEY = os.environ.get("COSMOS_API_KEY", "").strip()
COSMOS_MODEL = os.environ.get("COSMOS_MODEL", "cosmos-reason-2").strip() or "cosmos-reason-2"


def is_configured() -> bool:
    """True if both API URL and key are set."""
    return bool(COSMOS_API_URL and COSMOS_API_KEY)


def _mock_response(context: ContextPayload) -> CosmosResponsePayload:
    """Generate a zone-aware mock response for spatial reasoning demo."""
    sensors = context.get("sensors", {})
    devices = context.get("devices", {})
    alerts = context.get("alerts", {})
    humidity = sensors.get("humidityPct", 50.0)
    soil = sensors.get("soilMoisturePct", 40.0)
    dry_zones = alerts.get("dryZones", [])
    shaded_zones = alerts.get("shadedZones", [])

    recommendations: list[dict[str, Any]] = []
    explanation_parts = []

    # Zone-aware reasoning
    if dry_zones:
        explanation_parts.append(
            f"SPATIAL ANALYSIS: Detected dry zones at {', '.join(dry_zones)}. "
            f"These zones show soil moisture below 30%, indicating water stress. "
            f"The affected areas are visible in the greenhouse image as potentially wilted plants."
        )
        recommendations.append({
            "action": "set_valve",
            "value": 1.0,
            "why": f"Irrigate dry zones: {', '.join(dry_zones)}. Soil moisture critically low.",
            "confidence": 0.95,
        })
    elif soil < 30:
        explanation_parts.append(f"Global soil moisture is low ({soil}%), irrigation recommended.")
        recommendations.append({
            "action": "set_valve",
            "value": 1.0,
            "why": f"Global soil moisture at {soil}%; irrigate to prevent stress.",
            "confidence": 0.9,
        })
    else:
        recommendations.append({
            "action": "set_valve",
            "value": 0.0,
            "why": "Soil moisture levels adequate across all zones.",
            "confidence": 0.9,
        })

    if shaded_zones:
        explanation_parts.append(
            f"Low light detected in zones: {', '.join(shaded_zones)}. "
            "Consider adjusting canopy or supplemental lighting."
        )
        recommendations.append({
            "action": "send_alert",
            "value": None,
            "why": f"Shaded zones detected: {', '.join(shaded_zones)}. Manual inspection recommended.",
            "confidence": 0.8,
        })

    # Humidity control
    if humidity > 80:
        explanation_parts.append(f"High humidity ({humidity}%) detected. Increasing ventilation.")
        recommendations.append({
            "action": "set_fan",
            "value": 0.4,
            "why": f"Reduce humidity from {humidity}% to prevent fungal growth.",
            "confidence": 0.9,
        })
        recommendations.append({
            "action": "set_vent",
            "value": 20.0,
            "why": "Open vents for air circulation.",
            "confidence": 0.85,
        })
    else:
        recommendations.append({
            "action": "set_fan",
            "value": 0.0,
            "why": f"Humidity at {humidity}% is within optimal range.",
            "confidence": 0.9,
        })

    if not explanation_parts:
        explanation_parts.append("All zones appear healthy. No immediate action required.")

    return {
        "explanation": "[MOCK SPATIAL REASONING] " + " ".join(explanation_parts),
        "recommendations": recommendations,
    }


def build_request_payload(
    context: ContextPayload,
    image_base64: str,
    model: str = COSMOS_MODEL,
) -> dict[str, Any]:
    """
    Build the HTTP request body for the Cosmos endpoint.
    Isolated so you can adjust format for different API shapes (e.g. OpenAI-compatible
    chat/completions with vision, or custom vision field).
    """
    context_str = json.dumps(context, indent=2)

    # Extract zone alerts for the prompt
    alerts = context.get("alerts", {})
    dry_zones = alerts.get("dryZones", [])
    shaded_zones = alerts.get("shadedZones", [])

    zone_alert_text = ""
    if dry_zones or shaded_zones:
        zone_alert_text = "\n\nSPATIAL ALERTS:\n"
        if dry_zones:
            zone_alert_text += f"- DRY ZONES (need irrigation): {', '.join(dry_zones)}\n"
        if shaded_zones:
            zone_alert_text += f"- SHADED ZONES (low light): {', '.join(shaded_zones)}\n"
        zone_alert_text += "Reference these zones in your explanation to demonstrate spatial reasoning.\n"

    instructions = (
        "You are GreenhouseBot, an AI that performs SPATIAL REASONING over a digital twin greenhouse. "
        "The greenhouse has 8 beds (Bed_01 to Bed_08), each divided into 3 zones (A=north, B=center, C=south). "
        "You receive an image of the greenhouse AND zone-level telemetry data.\n\n"
        "YOUR TASK: Analyze the image and telemetry to identify problems at the ZONE level, "
        "explain the spatial location of issues (e.g., 'Zone B03-C in the middle-left of the greenhouse appears dry'), "
        "and recommend targeted actions.\n"
        f"{zone_alert_text}\n"
        "Return JSON only, no other text, with this exact shape:\n"
        '{"explanation": "string describing spatial observations and reasoning", '
        '"recommendations": [{"action": "set_fan"|"set_vent"|"set_valve"|"send_alert"|"no_action", '
        '"value": number|null, "why": "string with zone references", "confidence": number}]}\n\n'
        "Actions: set_fan (0-1), set_vent (0-100 degrees), set_valve (0-1 flow). "
        "Mention specific zone IDs (like B03-C) in your explanation and recommendations."
    )
    # Common OpenAI-compatible vision format; adjust if your endpoint differs
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Context (JSON):\n{context_str}\n\n{instructions}"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                },
            ],
        },
    ]
    return {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
    }


def call_cosmos(
    context: ContextPayload,
    image_base64: str,
) -> tuple[CosmosResponsePayload, dict[str, Any] | None]:
    """
    Call Cosmos Reason 2 (or mock). Returns (parsed response, raw response or None).
    """
    if not is_configured():
        payload = _mock_response(context)
        return payload, None

    try:
        import requests
    except ImportError:
        return _mock_response(context), None

    body = build_request_payload(context, image_base64)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {COSMOS_API_KEY}",
    }
    try:
        r = requests.post(COSMOS_API_URL, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        return (
            {
                "explanation": f"API call failed: {e}",
                "recommendations": [],
            },
            None,
        )

    # Extract content from common chat completion shape (choices[0].message.content)
    content = None
    if "choices" in raw and isinstance(raw["choices"], list) and len(raw["choices"]) > 0:
        msg = raw["choices"][0].get("message", {})
        content = msg.get("content") if isinstance(msg, dict) else None
    if not content:
        return parse_response(raw), raw

    # Parse JSON from model output
    try:
        if isinstance(content, str):
            # Allow markdown code block
            s = content.strip()
            if s.startswith("```"):
                lines = s.split("\n")
                for i, line in enumerate(lines):
                    if line.strip().startswith("```"):
                        s = "\n".join(lines[i + 1 :])
                        break
                if s.strip().endswith("```"):
                    s = s.strip()[:-3].strip()
            parsed = json.loads(s)
        else:
            parsed = content if isinstance(content, dict) else {}
        return parse_response(parsed), raw
    except json.JSONDecodeError:
        return (
            {"explanation": content if isinstance(content, str) else str(content), "recommendations": []},
            raw,
        )
