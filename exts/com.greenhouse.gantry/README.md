# Greenhouse Gantry + Cosmos extension

Isaac Sim extension for positioning the plant-inspection gantry, selecting and
capturing its camera, submitting one frame to the existing Cosmos 3 client, and
requiring operator approval before supported commands reach the runtime layer.

The panel also provides bounded fake temperature, humidity, and soil-moisture
readings plus buttons for the three contexts in `demo/scenario_*.json`. Applying
a reading or loading a scenario writes aggregate sensor values to
`usd/runtime/live_state.usda`; the selected context is then used by the next
Cosmos analysis.

The **Manual greenhouse controls** section operates independently of Cosmos:
it turns all three fans on or off, enables or disables the sprinkler effect,
and opens or closes both side-curtain windows. Each action is saved immediately
to the runtime layer. While the extension is enabled, it also drives the three
fan rotor transforms from `command:speed`; **Off** freezes them at their current
angle, including when the animation-preview stage is open.
In `greenhouse_animation_preview.usda`, the sprinkler controls also own the
visibility of all nine deterministic particle-effect containers: **On** shows
the animated spray and **Off** hides it immediately.
The window controls smoothly retract or restore both side-curtain transforms
over two seconds while preserving their authored base transforms. The closed
endpoint extends the curtain to the floor (`xformOp:scale.z = -1.46`).

## Enable in Isaac Sim

1. Open **Window > Extensions**.
2. Open the Extensions settings menu and add this repository's `exts` directory
   to the extension search paths.
3. Search for **Greenhouse Gantry and Cosmos** and enable it.
4. Open `usd/scenes/greenhouse_main.usda`.

The extension uses `COSMOS_API_URL`, `COSMOS_API_KEY`, and `COSMOS_MODEL` from
the Isaac Sim process environment. Without an endpoint it intentionally uses
the repository's mock reasoner.

The gantry controls author the current stage edit target. For a shot, select a
shot/animation layer before moving it. Approved model recommendations are
always redirected to `usd/runtime/live_state.usda`.
