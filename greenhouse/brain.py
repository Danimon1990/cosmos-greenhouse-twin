"""
Rule-based controller (brain) for greenhouse actuators.

Sets fan, vent, and water_valve from environment and zone state.
Does not overwrite other state fields.
"""


def step(state: dict) -> None:
    """
    Apply controller rules to state["actuators"]. Modifies state in place.

    Rules:
    - If temp > 26 OR humidity > 75: fan=0.7, vent=0.4
    - If temp < 18: fan=0.1, vent=0.0
    - If any zone soil_moisture < 0.30: water_valve=true
    - Else: water_valve=false
    """
    env = state["environment"]
    zones = state["zones"]
    actuators = state["actuators"]

    temp = env.get("temperature_c", 22.0)
    humidity = env.get("humidity_percent", 50.0)

    # Temperature and humidity rules
    if temp > 26 or humidity > 75:
        actuators["fan"] = 0.7
        actuators["vent"] = 0.4
    elif temp < 18:
        actuators["fan"] = 0.1
        actuators["vent"] = 0.0
    else:
        # Middle band: leave fan/vent as-is or set mild defaults
        if "fan" not in actuators or actuators["fan"] is None:
            actuators["fan"] = 0.0
        if "vent" not in actuators or actuators["vent"] is None:
            actuators["vent"] = 0.0

    # Clamp fan and vent to [0, 1]
    actuators["fan"] = max(0.0, min(1.0, float(actuators["fan"])))
    actuators["vent"] = max(0.0, min(1.0, float(actuators["vent"])))

    # Water rule: any zone dry -> open valve
    any_dry = any(z.get("soil_moisture", 0.5) < 0.30 for z in zones)
    actuators["water_valve"] = any_dry
