---
name: isaac-sim-greenhouse-readiness
description: Prepare or review greenhouse and robot assets for Isaac Sim, including collision geometry, rigid bodies, joints, articulations, sensors, semantic labels, navigation clearance, animation ownership, and simulation scenarios. Use after or alongside USD export; do not use for purely visual rendering work.
---

# Isaac Sim Greenhouse Readiness

Build simulation behavior in USD/Isaac Sim unless a Blender-authored property has a reliable, tested USD mapping. Treat Blender as the source for geometry, materials, collection semantics, pivots, and simple transform animation—not as the authority for PhysX configuration.

## Import boundary

Before export, require clean object names, applied scale where appropriate, intentional origins/pivots, useful collections, real-world dimensions, and separate render and collision candidates. Preserve joints and animation only when an export test proves that the intended USD representation survives correctly.

After export, author Isaac/PhysX behavior in stronger, non-destructive USD layers so geometry can be re-exported without destroying simulation work.

## Simulation classification

Classify each component before adding physics:

- Static collider: greenhouse frame, beds, floor, fixed utilities.
- Animated or kinematic collider: doors, vents, curtains, and other commanded infrastructure when forces do not drive them.
- Rigid body: freely moving props or detachable tools.
- Articulation: the mobile robot and mechanisms that require joint solving.
- Visual effect: water spray particles or other effects that do not need fluid dynamics.

Do not add rigid bodies indiscriminately. Prefer simple, stable collision approximations and exclude tiny visual details from collision.

## Project checks

- Confirm meters, up axis, mass scale, gravity, and material units.
- Keep collision meshes independently replaceable from render meshes.
- Verify door, vent, curtain, fan, wheel, and tool pivots before joint authoring.
- Define robot paths, turning clearance, restricted areas, docking poses, and attachment frames explicitly.
- Give RTX/OVRTX sensors stable mount prims and semantic labels.
- Separate deterministic actuator animation from sensor capture and presentation animation.
- Test contact stability, collision gaps, joint limits, reset behavior, and reproducibility in a minimal scenario before composing the full greenhouse.

## Water and fans

Use transform animation or commanded angular velocity for visible fan motion according to the scenario. Use a visual particle system for nine sprinkler streams unless the task explicitly requires computational fluid simulation. Keep irrigation state, particle emission, soil response, and rendered wetness as separate signals so Cosmos can command and observe them independently.
