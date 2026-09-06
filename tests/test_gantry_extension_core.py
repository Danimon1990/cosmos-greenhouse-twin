import importlib.util
from pathlib import Path

import pytest


MODULE = (
    Path(__file__).resolve().parents[1]
    / "exts/com.greenhouse.gantry/com/greenhouse/gantry/core.py"
)
SPEC = importlib.util.spec_from_file_location("gantry_core", MODULE)
core = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(core)


def test_clamp():
    assert core.clamp(-20, (-7.4, 7.4)) == -7.4
    assert core.clamp(3.2, (-7.4, 7.4)) == 3.2
    assert core.clamp(20, (-7.4, 7.4)) == 7.4


def test_advance_toward_moves_without_overshoot():
    assert core.advance_toward(0.0, 2.0, 1.5, 0.5) == 0.75
    assert core.advance_toward(1.8, 2.0, 1.5, 0.5) == 2.0
    assert core.advance_toward(2.0, -1.0, 2.0, 0.5) == 1.0
    assert core.advance_toward(2.0, -1.0, 2.0, 2.0) == -1.0


def test_bed_scan_lanes_cover_all_adjacent_bed_pairs():
    assert len(core.BED_SCAN_LANES) == 7
    assert core.bed_scan_lane(1)[1] == ("Bed_01", "Bed_02")
    assert core.bed_scan_lane(4) == (4, ("Bed_04", "Bed_05"), -1.75)
    assert core.bed_scan_lane(7)[1] == ("Bed_07", "Bed_08")
    with pytest.raises(ValueError):
        core.bed_scan_lane(8)


def test_context_with_inspection_identifies_camera_visible_beds():
    original = {"zones": [{"zoneId": "B04-B"}]}
    updated = core.context_with_inspection(original, 4, 20.0)
    assert updated["inspection"] == {
        "camera": "PlantScanCamera",
        "scanLane": 4,
        "visibleBeds": ["Bed_04", "Bed_05"],
        "cameraCarriageXM": -1.75,
        "longitudinalYM": 7.4,
    }
    assert "inspection" not in original


def test_normalized_sensor_values_clamps_readings():
    assert core.normalized_sensor_values(-30, 88, 120) == {
        "temperatureC": -20.0,
        "humidityPct": 88.0,
        "soilMoisturePct": 100.0,
    }


def test_context_with_sensor_values_preserves_scenario_data():
    original = {"sensors": {"temperatureC": 10}, "zones": [{"zoneId": "B03-C"}]}
    readings = {
        "temperatureC": 26.0,
        "humidityPct": 50.0,
        "soilMoisturePct": 35.0,
    }
    updated = core.context_with_sensor_values(original, readings)
    assert updated["sensors"] == readings
    assert updated["zones"] == original["zones"]
    assert original["sensors"] == {"temperatureC": 10}


def test_manual_actuator_values():
    assert core.manual_actuator_values("fans", True) == {"speed": 1.0}
    assert core.manual_actuator_values("fans", False) == {"speed": 0.0}
    assert core.manual_actuator_values("sprinklers", True) == {
        "sprayEnabled": True,
        "flow": 0.75,
    }
    assert core.manual_actuator_values("sprinklers", False) == {
        "sprayEnabled": False,
        "flow": 0.0,
    }
    assert core.manual_actuator_values("windows", True) == {"openRatio": 1.0}
    assert core.manual_actuator_values("windows", False) == {"openRatio": 0.0}


def test_advance_fan_angle_obeys_speed_and_stops_at_zero():
    assert core.advance_fan_angle(45.0, 0.0, 1.0) == 45.0
    assert core.advance_fan_angle(45.0, 0.5, 0.5) == 225.0
    assert core.advance_fan_angle(350.0, 1.0, 0.1) == 62.0
    assert core.advance_fan_angle(20.0, 2.0, 0.5) == 20.0


def test_sprinkler_visibility_tokens():
    assert core.sprinkler_visibility(True) == "inherited"
    assert core.sprinkler_visibility(False) == "invisible"

def test_window_ratio_moves_smoothly_and_stops_at_target():
    assert core.advance_ratio(0.0, 1.0, 0.5) == 0.25
    assert core.advance_ratio(0.9, 1.0, 0.5) == 1.0
    assert core.advance_ratio(1.0, 0.0, 0.5) == 0.75

def test_curtain_scale_retracts_as_window_opens():
    assert core.curtain_scale_z(0.0) == -1.46
    assert core.curtain_scale_z(0.5) == pytest.approx(-0.745)
    assert core.curtain_scale_z(1.0) == pytest.approx(-0.03)


def test_recommendation_validation():
    payload = {
        "recommendations": [
            {"action": "set_fan", "value": 0.4},
            {"action": "set_vent", "value": 101},
            {"action": "set_valve", "value": 1},
            {"action": "unknown", "value": 0},
            {"action": "no_action", "value": None},
        ]
    }
    assert core.validated_recommendations(payload) == [
        {"action": "set_fan", "value": 0.4},
        {"action": "set_valve", "value": 1},
        {"action": "no_action", "value": None},
    ]
