from __future__ import annotations

from typing import Any

GANTRY_PATH = "/World/Sensors/PlantInspectionGantry"
HORIZONTAL_MOUNT_PATH = f"{GANTRY_PATH}/Horizontal_Mount"
CAM_MOUNT_PATH = f"{HORIZONTAL_MOUNT_PATH}/Cam_mount"
CAMERA_PATH = f"{CAM_MOUNT_PATH}/PlantScanCamera"

LONGITUDINAL_LIMITS = (-7.4, 7.4)
CAMERA_LIMITS = (-5.75, 5.75)
GANTRY_METERS_PER_SECOND = 2.0
CAMERA_METERS_PER_SECOND = 1.5

# Seven camera lanes look between the greenhouse's eight physical beds.
# Lane 4 preserves the user-calibrated current view of Beds 04 and 05.
BED_SCAN_LANES = (
    (1, ("Bed_01", "Bed_02"), -5.75),
    (2, ("Bed_02", "Bed_03"), -4.85),
    (3, ("Bed_03", "Bed_04"), -3.30),
    (4, ("Bed_04", "Bed_05"), -1.75),
    (5, ("Bed_05", "Bed_06"), -0.20),
    (6, ("Bed_06", "Bed_07"), 1.35),
    (7, ("Bed_07", "Bed_08"), 2.08),
)
SENSOR_LIMITS = {
    "temperatureC": (-20.0, 60.0),
    "humidityPct": (0.0, 100.0),
    "soilMoisturePct": (0.0, 100.0),
}

FAN_DEGREES_PER_SECOND = 720.0
CURTAIN_CLOSED_SCALE_Z = -1.46
CURTAIN_OPEN_SCALE_Z = -0.03


def clamp(value: float, limits: tuple[float, float]) -> float:
    return max(limits[0], min(limits[1], float(value)))


def advance_toward(
    current: float, target: float, speed: float, delta_seconds: float
) -> float:
    """Advance one linear gantry axis without overshooting its target."""
    current = float(current)
    target = float(target)
    step = max(0.0, float(speed)) * max(0.0, float(delta_seconds))
    if current < target:
        return min(target, current + step)
    return max(target, current - step)


def bed_scan_lane(lane_number: int) -> tuple[int, tuple[str, str], float]:
    """Return one calibrated adjacent-bed scan lane."""
    if not 1 <= int(lane_number) <= len(BED_SCAN_LANES):
        raise ValueError(f"Unknown bed scan lane: {lane_number}")
    return BED_SCAN_LANES[int(lane_number) - 1]


def context_with_inspection(
    context: dict[str, Any], lane_number: int, longitudinal_y: float
) -> dict[str, Any]:
    """Add the scan camera pose and visible beds to a Cosmos context copy."""
    lane, visible_beds, camera_x = bed_scan_lane(lane_number)
    updated = dict(context)
    updated["inspection"] = {
        "camera": "PlantScanCamera",
        "scanLane": lane,
        "visibleBeds": list(visible_beds),
        "cameraCarriageXM": camera_x,
        "longitudinalYM": clamp(longitudinal_y, LONGITUDINAL_LIMITS),
    }
    return updated


def normalized_sensor_values(
    temperature_c: float, humidity_pct: float, soil_moisture_pct: float
) -> dict[str, float]:
    """Return bounded fake readings using the demo/Cosmos context field names."""
    return {
        "temperatureC": clamp(temperature_c, SENSOR_LIMITS["temperatureC"]),
        "humidityPct": clamp(humidity_pct, SENSOR_LIMITS["humidityPct"]),
        "soilMoisturePct": clamp(
            soil_moisture_pct, SENSOR_LIMITS["soilMoisturePct"]
        ),
    }


def context_with_sensor_values(
    context: dict[str, Any], sensor_values: dict[str, float]
) -> dict[str, Any]:
    """Copy a scenario context and replace only its aggregate sensor readings."""
    updated = dict(context)
    updated["sensors"] = dict(sensor_values)
    return updated


def manual_actuator_values(actuator: str, enabled: bool) -> dict[str, float | bool]:
    """Return the runtime command values for one manual UI actuator group."""
    if actuator == "fans":
        return {"speed": 1.0 if enabled else 0.0}
    if actuator == "sprinklers":
        return {
            "sprayEnabled": enabled,
            "flow": 0.75 if enabled else 0.0,
        }
    if actuator == "windows":
        return {"openRatio": 1.0 if enabled else 0.0}
    raise ValueError(f"Unknown actuator group: {actuator}")


def advance_fan_angle(angle: float, speed: float, delta_seconds: float) -> float:
    """Advance a rotor angle from a normalized speed command."""
    bounded_speed = clamp(speed, (0.0, 1.0))
    bounded_delta = max(0.0, float(delta_seconds))
    return (float(angle) + bounded_speed * FAN_DEGREES_PER_SECOND * bounded_delta) % 360.0


def sprinkler_visibility(enabled: bool) -> str:
    """Return the USD visibility token for the sprinkler effect containers."""
    return "inherited" if enabled else "invisible"

def advance_ratio(current: float, target: float, delta_seconds: float) -> float:
    """Move a normalized actuator ratio toward its target at 0.5 per second."""
    current = clamp(current, (0.0, 1.0))
    target = clamp(target, (0.0, 1.0))
    step = max(0.0, float(delta_seconds)) * 0.5
    if current < target:
        return min(target, current + step)
    return max(target, current - step)

def curtain_scale_z(open_ratio: float) -> float:
    """Interpolate from floor-length closed scale to the retracted open scale."""
    ratio = clamp(open_ratio, (0.0, 1.0))
    return CURTAIN_CLOSED_SCALE_Z + ratio * (
        CURTAIN_OPEN_SCALE_Z - CURTAIN_CLOSED_SCALE_Z
    )


def recommendation_is_actionable(rec: dict[str, Any]) -> bool:
    action = rec.get("action")
    value = rec.get("value")
    if action == "set_fan":
        return isinstance(value, (int, float)) and 0 <= value <= 1
    if action == "set_vent":
        return isinstance(value, (int, float)) and 0 <= value <= 100
    if action == "set_valve":
        return isinstance(value, (int, float)) and 0 <= value <= 1
    return action in {"send_alert", "no_action"}


def validated_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = payload.get("recommendations", [])
    if not isinstance(recommendations, list):
        return []
    return [rec for rec in recommendations if isinstance(rec, dict) and recommendation_is_actionable(rec)]
