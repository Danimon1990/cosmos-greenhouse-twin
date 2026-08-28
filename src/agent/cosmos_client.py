"""
Cosmos 3 Reasoner HTTP client for the greenhouse digital twin.

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
COSMOS_MODEL = (
    os.environ.get("COSMOS_MODEL", "nvidia/cosmos3-nano-reasoner").strip()
    or "nvidia/cosmos3-nano-reasoner"
)
COSMOS_TIMEOUT_SECONDS = float(os.environ.get("COSMOS_TIMEOUT_SECONDS", "120"))


def is_configured() -> bool:
    """True if API URL is set. Key optional for localhost (e.g. local NIM/vLLM)."""
    if not COSMOS_API_URL:
        return False
    try:
        from urllib.parse import urlparse
        host = urlparse(COSMOS_API_URL).hostname or ""
        if host in ("127.0.0.1", "localhost", "::1"):
            return True  # local server often has no auth
    except Exception:
        pass
    return bool(COSMOS_API_KEY)


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


def _image_data_uri(image_base64: str) -> str:
    """Build a correctly typed data URI for the PNG/JPEG inputs used by Cosmos 3."""
    try:
        prefix = base64.b64decode(image_base64[:32], validate=False)
    except Exception:
        prefix = b""
    media_type = "image/png" if prefix.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
    return f"data:{media_type};base64,{image_base64}"


def build_request_payload(
    context: ContextPayload,
    image_base64: str,
    model: str = COSMOS_MODEL,
) -> dict[str, Any]:
    """Build an OpenAI-compatible Cosmos 3 Reasoner chat-completions request."""
    context_str = json.dumps(context, indent=2)

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
        zone_alert_text += "Reference these zones in your explanation.\n"

    instructions = (
        "Analyze the greenhouse image and zone telemetry as a physical-AI reasoner. "
        "Identify problems at the zone level, explain their spatial location, and propose targeted actions.\n"
        f"{zone_alert_text}\n"
        "After reasoning, return a JSON object with exactly this shape:\n"
        '{"explanation": "spatial observations grounded in image and telemetry", '
        '"recommendations": [{"action": "set_fan"|"set_vent"|"set_valve"|"send_alert"|"no_action", '
        '"value": number|null, "why": "reason with zone references", "confidence": number}]}\n'
        "Action ranges: set_fan 0-1, set_vent 0-100 degrees, set_valve 0-1.\n\n"
        "Answer using this format:\n<think>\nYour analysis.\n</think>\n"
        "Write the JSON object immediately after </think>, without prose or Markdown fences."
    )

    # NVIDIA's Cosmos 3 prompt guide requires media before user text.
    messages = [
        {
            "role": "system",
            "content": "You are a helpful physical-AI assistant for a robot-assisted greenhouse.",
        },
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _image_data_uri(image_base64)}},
                {"type": "text", "text": f"Context (JSON):\n{context_str}\n\n{instructions}"},
            ],
        },
    ]
    return {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.6,
        "top_p": 0.95,
        "presence_penalty": 0.0,
        "seed": 0,
        "stream": False,
    }


def call_cosmos(
    context: ContextPayload,
    image_base64: str,
) -> tuple[CosmosResponsePayload, dict[str, Any] | None]:
    """
    Call Cosmos 3 Reasoner (or mock). Returns (parsed response, raw response or None).
    """
    if not is_configured():
        payload = _mock_response(context)
        return payload, None

    try:
        import requests
    except ImportError:
        return _mock_response(context), None

    body = build_request_payload(context, image_base64)
    headers = {"Content-Type": "application/json"}
    if COSMOS_API_KEY:
        headers["Authorization"] = f"Bearer {COSMOS_API_KEY}"
    try:
        r = requests.post(COSMOS_API_URL, json=body, headers=headers, timeout=COSMOS_TIMEOUT_SECONDS)
        r.raise_for_status()
        if not r.text or not r.text.strip():
            return (
                {
                    "explanation": f"API call failed: empty response body (status {r.status_code})",
                    "recommendations": [],
                },
                None,
            )
        try:
            raw = r.json()
        except json.JSONDecodeError as je:
            preview = (r.text[:500] + "…") if len(r.text) > 500 else r.text
            return (
                {
                    "explanation": f"API call failed: response is not JSON (status {r.status_code}). First 500 chars: {preview!r}",
                    "recommendations": [],
                },
                None,
            )
    except requests.exceptions.RequestException as e:
        err_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                err_msg = f"{e.response.status_code} {e.response.reason}: {(e.response.text or '')[:300]}"
            except Exception:
                pass
        hint = ""
        if "reset" in err_msg.lower() or "aborted" in err_msg.lower():
            hint = " (Server may have closed the connection: check NIM/vLLM logs; try --max-image-size 1024 to send a smaller image.)"
        return (
            {
                "explanation": f"API call failed: {err_msg}{hint}",
                "recommendations": [],
            },
            None,
        )
    except Exception as e:
        err_msg = str(e)
        hint = ""
        if "reset" in err_msg.lower() or "aborted" in err_msg.lower():
            hint = " (Check server logs; try --max-image-size 1024.)"
        return (
            {
                "explanation": f"API call failed: {err_msg}{hint}",
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
            s = content.strip()

            # Cosmos 3 reasoning is prompt-controlled and emitted in <think> tags.
            import re
            s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()

            # Extract JSON from markdown code block (```json ... ```)
            code_block_match = re.search(r"```(?:json)?\s*\n(.*?)```", s, flags=re.DOTALL)
            if code_block_match:
                s = code_block_match.group(1).strip()
            elif s.startswith("```"):
                # Fallback: strip opening/closing fences
                lines = s.split("\n")
                s = "\n".join(lines[1:])
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
