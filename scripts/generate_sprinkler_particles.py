#!/usr/bin/env python3
"""Generate a deterministic nine-emitter UsdGeomPoints sprinkler animation.

This prototype intentionally uses standard OpenUSD rather than PhysX schemas:
the checked local USD runtime does not expose PhysxSchema. The generated points
remain inspectable in any Hydra-based USD viewer and can later be replaced by a
PhysX particle set without changing the sprinkler control interface.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path


DEFAULT_OUTPUT = Path("usd/shots/sprinkler_particle_preview.usda")
PARTICLE_COUNT = 192
START_FRAME = 0
END_FRAME = 240
FRAME_STEP = 2
FPS = 24.0
LIFETIME_SECONDS = 0.82
GRAVITY = 4.5
BASE_DOWNWARD_SPEED = 0.35
MAX_COVERAGE_RADIUS = 3.2
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))

# World-space nozzle locations read from the production greenhouse assembly.
# The 3 x 3 layout spans the growing area; the wide circular footprints overlap
# so the outside emitters also reach the greenhouse edges and corners.
SPRINKLERS = (
    ("Sprinkler_01_02", "GH_Sprinkler_Nozzle_01_02", (-3.1, 2.0952, 5.6667)),
    ("Sprinkler_01_04", "GH_Sprinkler_Nozzle_01_04", (-3.1, 2.0952, 0.0)),
    ("Sprinkler_01_06", "GH_Sprinkler_Nozzle_01_06", (-3.1, 2.0952, -5.6667)),
    ("Sprinkler_02_02", "GH_Sprinkler_Nozzle_02_02", (0.0, 2.0952, 5.6667)),
    ("Sprinkler_02_04", "GH_Sprinkler_Nozzle_02_04", (0.0, 2.0952, 0.0)),
    ("Sprinkler_02_06", "GH_Sprinkler_Nozzle_02_06", (0.0, 2.0952, -5.6667)),
    ("Sprinkler_03_02", "GH_Sprinkler_Nozzle_03_02", (3.1, 2.0952, 5.6667)),
    ("Sprinkler_03_04", "GH_Sprinkler_Nozzle_03_04", (3.1, 2.0952, 0.0)),
    ("Sprinkler_03_06", "GH_Sprinkler_Nozzle_03_06", (3.1, 2.0952, -5.6667)),
)


def _particle_age(index: int, frame: int) -> float:
    time_seconds = frame / FPS
    emission_offset = (index / PARTICLE_COUNT) * LIFETIME_SECONDS
    return (time_seconds + emission_offset) % LIFETIME_SECONDS


def _particle_position(index: int, frame: int) -> tuple[float, float, float]:
    """Return one recycled top-down droplet in emitter-local coordinates."""
    age = _particle_age(index, frame)

    # Stable variation avoids a perfectly mechanical ring while preserving a
    # deterministic result on every regeneration.
    downward_speed = BASE_DOWNWARD_SPEED * (
        0.92 + 0.16 * ((index * 37) % 101) / 100.0
    )
    radial_variation = (
        0.88 + 0.24 * ((index * 53) % 97) / 96.0
    )
    # Keep the stream tight near the nozzle and widen it close to the beds.
    # Squared normalized age avoids the sideways burst of a radial velocity.
    angle = index * GOLDEN_ANGLE + age * 1.35
    fall_progress = age / LIFETIME_SECONDS
    radius = 0.025 + MAX_COVERAGE_RADIUS * radial_variation * fall_progress**2

    x = radius * math.cos(angle)
    y = -downward_speed * age - 0.5 * GRAVITY * age * age
    z = radius * math.sin(angle)
    return x, y, z


def _particle_width(index: int, frame: int) -> float:
    """Fade recycled droplets out at death and back in after emission."""
    age = _particle_age(index, frame)
    fade_seconds = 0.08
    fade_in = min(1.0, age / fade_seconds)
    fade_out = min(1.0, (LIFETIME_SECONDS - age) / fade_seconds)
    variation = 0.85 + 0.3 * ((index * 29) % 89) / 88.0
    return 0.022 * variation * max(0.0, min(fade_in, fade_out))


def _format_points(frame: int) -> str:
    values = []
    for index in range(PARTICLE_COUNT):
        x, y, z = _particle_position(index, frame)
        values.append(f"({x:.5f}, {y:.5f}, {z:.5f})")
    return ", ".join(values)


def _format_widths(frame: int) -> str:
    return ", ".join(
        f"{_particle_width(index, frame):.5f}" for index in range(PARTICLE_COUNT)
    )


def build_layer() -> str:
    samples = []
    width_samples = []
    for frame in range(START_FRAME, END_FRAME + 1, FRAME_STEP):
        samples.append(f"                {frame}: [{_format_points(frame)}],")
        width_samples.append(f"                {frame}: [{_format_widths(frame)}],")

    ids = ", ".join(str(index) for index in range(PARTICLE_COUNT))
    emitters = []
    for emitter_name, nozzle_name, position in SPRINKLERS:
        x, y, z = position
        # The exchange stage carries a legacy +90-degree X rotation on /World.
        # Convert desired Y-up world coordinates back into that parent's local
        # space, then rotate the emitter so droplet-local axes remain Y-up.
        local_x, local_y, local_z = x, -z, y
        emitters.append(
            f'''            def Xform "{emitter_name}" (
                references = </World/Effects/Sprinklers/_EmitterPrototype>
            )
            {{
                custom uniform token animation:owner = "sprinklerParticlePreview"
                custom uniform token effect:representation = "deterministicUsdGeomPoints"
                custom float emitter:coverageRadius = 3.6
                custom int emitter:particleCount = {PARTICLE_COUNT}
                custom float emitter:flow = 1
                custom float emitter:lifetimeSeconds = {LIFETIME_SECONDS}
                custom uniform string emitter:sourcePrim = "/World/Environment/Greenhouse/Irrigation/{nozzle_name}"
                double3 xformOp:translate = ({local_x:.4f}, {local_y:.4f}, {local_z:.4f})
                double xformOp:rotateX = 90
                uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateX"]
            }}'''
        )

    return f'''#usda 1.0
(
    doc = "Generated deterministic wide-coverage particle preview for all nine greenhouse sprinklers. Regenerate with scripts/generate_sprinkler_particles.py."
    endTimeCode = {END_FRAME}
    framesPerSecond = {int(FPS)}
    metersPerUnit = 1
    startTimeCode = {START_FRAME}
    timeCodesPerSecond = {int(FPS)}
    upAxis = "Y"
)

over Xform "World"
{{
    over Scope "Effects"
    {{
        def Scope "Sprinklers"
        {{
            class Xform "_EmitterPrototype"
            {{
                def Points "Droplets"
                {{
                    point3f[] extent = [(-3.7, -1.9, -3.7), (3.7, 0.05, 3.7)]
                    int64[] ids = [{ids}]
                    point3f[] points.timeSamples = {{
{chr(10).join(samples)}
                    }}
                    color3f[] primvars:displayColor = [(0.18, 0.62, 1)]
                    float[] primvars:displayOpacity = [0.72]
                    float[] widths.timeSamples = {{
{chr(10).join(width_samples)}
                    }}
                }}
            }}

{chr(10).join(emitters)}
        }}
    }}
}}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_layer(), encoding="utf-8")
    print(
        f"Wrote {args.output} with {len(SPRINKLERS)} emitters, "
        f"{PARTICLE_COUNT} particles per emitter, and "
        f"{(END_FRAME - START_FRAME) // FRAME_STEP + 1} time samples"
    )


if __name__ == "__main__":
    main()
