"""
Create or initialize greenhouse/live_state.usda with prim hierarchy and attributes.

Run once to ensure the stage exists; usd_sync.py then writes values each step.
"""

from pathlib import Path

try:
    from pxr import Sdf, Usd
except ImportError as e:
    raise SystemExit(
        "pxr (OpenUSD) not found. Install with: pip install usd-core"
    ) from e

GREENHOUSE_DIR = Path(__file__).resolve().parent
DEFAULT_USD_PATH = GREENHOUSE_DIR / "live_state.usda"

# Prim paths
WORLD = "/World"
GREENHOUSE = "/World/Greenhouse"
ENVIRONMENT = "/World/Greenhouse/Environment"
ACTUATORS = "/World/Greenhouse/Actuators"
ZONES = "/World/Greenhouse/Zones"
BED_1 = "/World/Greenhouse/Zones/bed_1"
BED_2 = "/World/Greenhouse/Zones/bed_2"
BED_3 = "/World/Greenhouse/Zones/bed_3"


def _ensure_prim(stage: Usd.Stage, path: str, kind: str = "Scope") -> Usd.Prim:
    """Create prim if missing; return prim. World is Xform, rest Scope."""
    prim = stage.GetPrimAtPath(path)
    if prim.IsValid():
        return prim
    parent_path = path.rsplit("/", 1)[0]
    if parent_path:
        _ensure_prim(stage, parent_path)
    return stage.DefinePrim(path, kind)


def _add_attr(prim: Usd.Prim, name: str, type_name: Sdf.ValueTypeName, default_val):
    """Create attribute if missing and set default."""
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, type_name)
    if attr and default_val is not None:
        attr.Set(default_val)
    return attr


def ensure_stage(usd_path: str | Path) -> Path:
    """
    Create or open the stage at usd_path; create hierarchy and attributes if missing.
    Returns resolved path to the USD file.
    """
    path = Path(usd_path)
    if not path.is_absolute():
        path = GREENHOUSE_DIR / path.name
    path = path.resolve()

    if path.exists():
        stage = Usd.Stage.Open(str(path))
    else:
        stage = Usd.Stage.CreateNew(str(path))

    # Hierarchy: World = Xform, rest = Scope
    _ensure_prim(stage, WORLD, "Xform")
    stage.SetDefaultPrim(stage.GetPrimAtPath(WORLD))
    _ensure_prim(stage, GREENHOUSE)
    _ensure_prim(stage, ENVIRONMENT)
    _ensure_prim(stage, ACTUATORS)
    _ensure_prim(stage, ZONES)
    _ensure_prim(stage, BED_1)
    _ensure_prim(stage, BED_2)
    _ensure_prim(stage, BED_3)

    gh = stage.GetPrimAtPath(GREENHOUSE)
    env = stage.GetPrimAtPath(ENVIRONMENT)
    act = stage.GetPrimAtPath(ACTUATORS)

    # Greenhouse
    _add_attr(gh, "timestamp", Sdf.ValueTypeNames.String, "2026-02-14T12:00:00Z")

    # Environment
    _add_attr(env, "temperature_c", Sdf.ValueTypeNames.Double, 22.0)
    _add_attr(env, "humidity_percent", Sdf.ValueTypeNames.Double, 55.0)
    _add_attr(env, "co2_ppm", Sdf.ValueTypeNames.Double, 420.0)
    _add_attr(env, "light_lux", Sdf.ValueTypeNames.Double, 8000.0)

    # Actuators
    _add_attr(act, "fan", Sdf.ValueTypeNames.Double, 0.0)
    _add_attr(act, "vent", Sdf.ValueTypeNames.Double, 0.0)
    _add_attr(act, "water_valve", Sdf.ValueTypeNames.Bool, False)

    # Beds
    for bed_path in (BED_1, BED_2, BED_3):
        bed = stage.GetPrimAtPath(bed_path)
        _add_attr(bed, "crop", Sdf.ValueTypeNames.String, "lettuce")
        _add_attr(bed, "soil_moisture", Sdf.ValueTypeNames.Double, 0.5)
        _add_attr(bed, "plant_height_cm", Sdf.ValueTypeNames.Double, 12.0)
        _add_attr(bed, "health", Sdf.ValueTypeNames.String, "0.9")

    stage.GetRootLayer().Save()
    return path


if __name__ == "__main__":
    p = ensure_stage(DEFAULT_USD_PATH)
    print(f"Stage ready: {p}")
