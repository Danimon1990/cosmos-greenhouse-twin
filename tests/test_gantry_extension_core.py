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
