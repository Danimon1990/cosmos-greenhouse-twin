from __future__ import annotations

import asyncio
import base64
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import carb
import omni.ext
import omni.kit.app
import omni.ui as ui
import omni.usd
from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport
from pxr import Gf, Sdf

from .core import (
    BED_SCAN_LANES,
    CAMERA_LIMITS,
    CAMERA_METERS_PER_SECOND,
    CAMERA_PATH,
    CAM_MOUNT_PATH,
    GANTRY_METERS_PER_SECOND,
    HORIZONTAL_MOUNT_PATH,
    LONGITUDINAL_LIMITS,
    advance_toward,
    advance_fan_angle,
    advance_ratio,
    bed_scan_lane,
    clamp,
    context_with_inspection,
    context_with_sensor_values,
    curtain_scale_z,
    manual_actuator_values,
    normalized_sensor_values,
    sprinkler_visibility,
    validated_recommendations,
)

SENSOR_PATH = "/World/Environment/Greenhouse/Devices/Sensor_01"
SCENARIOS = (
    ("Dry zone", "scenario_1_dry_zone.json"),
    ("Humid + shaded", "scenario_2_humid_and_shaded.json"),
    ("Multi-crisis", "scenario_3_multi_crisis.json"),
)
SPRINKLER_EFFECT_PATHS = tuple(
    f"/World/Effects/Sprinklers/Sprinkler_{row:02d}_{column:02d}"
    for row in range(1, 4) for column in (2, 4, 6)
)


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "usd/scenes/greenhouse_main.usda").exists():
            return parent
    raise RuntimeError("Could not locate the cosmos-greenhouse-twin repository")


class GreenhouseGantryExtension(omni.ext.IExt):
    def on_startup(self, ext_id: str) -> None:
        self._ext_id = ext_id
        self._repo_root = _find_repo_root()
        self._window = ui.Window("Greenhouse Gantry + Cosmos", width=460, height=780)
        self._longitudinal_model = ui.SimpleFloatModel(0.0)
        self._camera_model = ui.SimpleFloatModel(-1.75)
        self._temperature_model = ui.SimpleFloatModel(28.0)
        self._humidity_model = ui.SimpleFloatModel(50.0)
        self._soil_model = ui.SimpleFloatModel(10.0)
        self._status_model = ui.SimpleStringModel("Ready. Open greenhouse_main.usda.")
        self._proposal_model = ui.SimpleStringModel("No Cosmos proposal yet.")
        self._proposal: dict[str, Any] | None = None
        self._context = self._load_context("test_context.json")
        self._task: asyncio.Task | None = None
        self._fan_angles = [0.0, 0.0, 0.0]
        self._fan_speed_override: float | None = None
        self._window_ratio_current = 0.0
        self._window_ratio_target = 0.0
        self._gantry_target: tuple[float, float] | None = None
        self._selected_scan_lane = 4
        self._update_sub = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(
                self._on_update, name="Greenhouse fan runtime driver"
            )
        )
        self._build_ui()

    def on_shutdown(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self._update_sub = None
        self._window = None

    def _on_update(self, event) -> None:
        """Drive fan rotor transforms from the current command every Kit frame."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            delta_seconds = float((event.payload or {}).get("dt", 0.0))
            previous = stage.GetEditTarget()
            try:
                # Session state stays stronger than preview time samples and unsaved.
                stage.SetEditTarget(stage.GetSessionLayer())
                self._update_gantry(stage, delta_seconds)
                for offset, index in enumerate(range(1, 4)):
                    fan_path = f"/World/Environment/Greenhouse/Ventilation/Fan_0{index}"
                    fan = stage.GetPrimAtPath(fan_path)
                    rotor = stage.GetPrimAtPath(f"{fan_path}/Fan_0{index}_Rotor")
                    if not fan or not rotor:
                        continue
                    speed_attr = fan.GetAttribute("command:speed")
                    speed = (
                        self._fan_speed_override
                        if self._fan_speed_override is not None
                        else float(speed_attr.Get() or 0.0)
                    )
                    self._fan_angles[offset] = advance_fan_angle(
                        self._fan_angles[offset], speed, delta_seconds
                    )
                    rotation = rotor.GetAttribute("xformOp:rotateY:actuation")
                    if rotation:
                        rotation.Set(self._fan_angles[offset])
                self._update_curtains(stage, delta_seconds)
            finally:
                stage.SetEditTarget(previous)
        except Exception as exc:
            carb.log_warn(f"[{self._ext_id}] Runtime animation update failed: {exc}")

    def _update_gantry(self, stage, delta_seconds: float) -> None:
        if self._gantry_target is None:
            return
        target_y, target_x = self._gantry_target
        horizontal = stage.GetPrimAtPath(HORIZONTAL_MOUNT_PATH)
        carriage = stage.GetPrimAtPath(CAM_MOUNT_PATH)
        if not horizontal or not carriage:
            self._gantry_target = None
            raise RuntimeError("Gantry motion prims are missing from the stage")
        horizontal_attr = horizontal.GetAttribute("xformOp:translate")
        carriage_attr = carriage.GetAttribute("xformOp:translate")
        horizontal_xyz = horizontal_attr.Get() if horizontal_attr else None
        carriage_xyz = carriage_attr.Get() if carriage_attr else None
        if horizontal_xyz is None or carriage_xyz is None:
            self._gantry_target = None
            raise RuntimeError("Gantry motion transforms are missing")

        next_y = advance_toward(
            horizontal_xyz[1], target_y, GANTRY_METERS_PER_SECOND, delta_seconds
        )
        next_x = advance_toward(
            carriage_xyz[0], target_x, CAMERA_METERS_PER_SECOND, delta_seconds
        )
        horizontal_attr.Set(
            Gf.Vec3d(float(horizontal_xyz[0]), next_y, float(horizontal_xyz[2]))
        )
        carriage_attr.Set(
            Gf.Vec3d(next_x, float(carriage_xyz[1]), float(carriage_xyz[2]))
        )
        self._longitudinal_model.set_value(next_y)
        self._camera_model.set_value(next_x)

        if abs(next_y - target_y) < 1e-5 and abs(next_x - target_x) < 1e-5:
            self._gantry_target = None
            lane, visible_beds, _camera_x = bed_scan_lane(self._selected_scan_lane)
            self._context = context_with_inspection(self._context, lane, target_y)
            self._status_model.set_value(
                f"Scan lane {lane} ready: {visible_beds[0]} and {visible_beds[1]} visible"
            )

    def _update_curtains(self, stage, delta_seconds: float) -> None:
        self._window_ratio_current = advance_ratio(
            self._window_ratio_current, self._window_ratio_target, delta_seconds
        )
        for side in ("L", "R"):
            curtain = stage.GetPrimAtPath(
                f"/World/Environment/Greenhouse/Ventilation/GH_Side_Curtain_{side}"
            )
            if not curtain:
                continue
            scale = curtain.GetAttribute("xformOp:scale")
            current = scale.Get() if scale else None
            if current is not None:
                scale.Set(Gf.Vec3f(float(current[0]), float(current[1]), curtain_scale_z(self._window_ratio_current)))

    def _build_ui(self) -> None:
        with self._window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=8, height=0):
                    ui.Label("Plant Inspection Gantry", height=28)
                    ui.Label("Adjacent-bed scan lanes")
                    with ui.HStack(height=30, spacing=4):
                        for lane, visible_beds, _x in BED_SCAN_LANES[:4]:
                            ui.Button(
                                f"{lane}: {visible_beds[0][-2:]}-{visible_beds[1][-2:]}",
                                clicked_fn=lambda n=lane: self._move_to_scan_lane(n),
                            )
                    with ui.HStack(height=30, spacing=4):
                        for lane, visible_beds, _x in BED_SCAN_LANES[4:]:
                            ui.Button(
                                f"{lane}: {visible_beds[0][-2:]}-{visible_beds[1][-2:]}",
                                clicked_fn=lambda n=lane: self._move_to_scan_lane(n),
                            )
                    ui.Label("Longitudinal position (local Y, meters)")
                    ui.FloatSlider(
                        model=self._longitudinal_model,
                        min=LONGITUDINAL_LIMITS[0],
                        max=LONGITUDINAL_LIMITS[1],
                        step=0.05,
                    )
                    ui.Label("Camera carriage (local X, meters)")
                    ui.FloatSlider(
                        model=self._camera_model,
                        min=CAMERA_LIMITS[0],
                        max=CAMERA_LIMITS[1],
                        step=0.05,
                    )
                    with ui.HStack(height=30, spacing=6):
                        ui.Button("Move to position", clicked_fn=self._apply_position)
                        ui.Button("Home", clicked_fn=self._home)
                    ui.Button("Use scan camera in viewport", height=30, clicked_fn=self._activate_camera)
                    ui.Separator(height=12)
                    ui.Label("Fake environmental sensors", height=28)
                    self._sensor_row("Temperature (C)", self._temperature_model, -20, 60)
                    self._sensor_row("Humidity (%)", self._humidity_model, 0, 100)
                    self._sensor_row("Soil moisture (%)", self._soil_model, 0, 100)
                    ui.Button("Apply fake sensors", height=30, clicked_fn=self._apply_fake_sensors)
                    ui.Label("Demo scenarios")
                    with ui.HStack(height=30, spacing=4):
                        for index, (label, _filename) in enumerate(SCENARIOS):
                            ui.Button(label, clicked_fn=lambda i=index: self._load_scenario(i))
                    ui.Separator(height=12)
                    ui.Label("Manual greenhouse controls", height=28)
                    self._actuator_row(
                        "Fans", "On", "Off",
                        lambda: self._set_manual_actuator("fans", True),
                        lambda: self._set_manual_actuator("fans", False),
                    )
                    self._actuator_row(
                        "Sprinklers", "On", "Off",
                        lambda: self._set_manual_actuator("sprinklers", True),
                        lambda: self._set_manual_actuator("sprinklers", False),
                    )
                    self._actuator_row(
                        "Windows", "Open", "Close",
                        lambda: self._set_manual_actuator("windows", True),
                        lambda: self._set_manual_actuator("windows", False),
                    )
                    ui.Separator(height=12)
                    ui.Label("Cosmos 3 inspection", height=28)
                    ui.Button("Capture frame and analyze", height=34, clicked_fn=self._start_analysis)
                    self._proposal_label = ui.Label(
                        self._proposal_model.as_string, word_wrap=True, height=220
                    )
                    self._proposal_model.add_value_changed_fn(
                        lambda model: setattr(self._proposal_label, "text", model.as_string)
                    )
                    ui.Button("Approve recommendations", height=34, clicked_fn=self._approve)
                    ui.Separator(height=12)
                    self._status_label = ui.Label(
                        self._status_model.as_string, word_wrap=True, height=70
                    )
                    self._status_model.add_value_changed_fn(
                        lambda model: setattr(self._status_label, "text", model.as_string)
                    )

    def _sensor_row(self, label: str, model, minimum: float, maximum: float) -> None:
        with ui.HStack(height=26, spacing=6):
            ui.Label(label, width=150)
            ui.FloatDrag(model=model, min=minimum, max=maximum, step=1.0)

    def _actuator_row(
        self, label: str, on_label: str, off_label: str, on_click, off_click
    ) -> None:
        with ui.HStack(height=30, spacing=6):
            ui.Label(label, width=150)
            ui.Button(on_label, clicked_fn=on_click)
            ui.Button(off_label, clicked_fn=off_click)

    def _load_context(self, filename: str) -> dict[str, Any]:
        return json.loads((self._repo_root / "demo" / filename).read_text())

    def _stage(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            raise RuntimeError("No USD stage is open")
        return stage

    def _set_translate_component(self, prim_path: str, component: int, value: float) -> None:
        prim = self._stage().GetPrimAtPath(prim_path)
        if not prim:
            raise RuntimeError(f"Missing gantry prim: {prim_path}")
        attr = prim.GetAttribute("xformOp:translate")
        current = attr.Get() if attr else None
        if current is None:
            raise RuntimeError(f"Missing xformOp:translate on {prim_path}")
        xyz = [float(current[0]), float(current[1]), float(current[2])]
        xyz[component] = value
        attr.Set(Gf.Vec3d(*xyz))

    def _apply_position(self) -> None:
        try:
            y = clamp(self._longitudinal_model.as_float, LONGITUDINAL_LIMITS)
            x = clamp(self._camera_model.as_float, CAMERA_LIMITS)
            self._gantry_target = (y, x)
            self._status_model.set_value(
                f"Moving gantry to Y={y:.2f} m and camera X={x:.2f} m"
            )
        except Exception as exc:
            self._fail(exc)

    def _move_to_scan_lane(self, lane_number: int) -> None:
        try:
            lane, visible_beds, camera_x = bed_scan_lane(lane_number)
            target_y = clamp(self._longitudinal_model.as_float, LONGITUDINAL_LIMITS)
            self._selected_scan_lane = lane
            self._camera_model.set_value(camera_x)
            self._gantry_target = (target_y, camera_x)
            self._status_model.set_value(
                f"Moving to scan lane {lane}: {visible_beds[0]} and {visible_beds[1]}"
            )
        except Exception as exc:
            self._fail(exc)

    def _home(self) -> None:
        self._longitudinal_model.set_value(0.0)
        self._camera_model.set_value(-1.75)
        self._apply_position()

    def _activate_camera(self) -> None:
        try:
            camera = self._stage().GetPrimAtPath(CAMERA_PATH)
            if not camera:
                raise RuntimeError(f"Scan camera not found: {CAMERA_PATH}")
            viewport = get_active_viewport()
            if not viewport:
                raise RuntimeError("No active viewport")
            viewport.set_active_camera(CAMERA_PATH)
            self._status_model.set_value("Viewport is using PlantScanCamera")
        except Exception as exc:
            self._fail(exc)

    def _write_sensor_values(self, values: dict[str, float]) -> None:
        stage = self._stage()
        previous = stage.GetEditTarget()
        try:
            runtime = self._runtime_layer(stage)
            stage.SetEditTarget(runtime)
            for name, value in values.items():
                self._set_command(
                    SENSOR_PATH, f"sensor:{name}", Sdf.ValueTypeNames.Float, value
                )
            runtime.Save()
        finally:
            stage.SetEditTarget(previous)

    def _apply_fake_sensors(self) -> None:
        try:
            values = normalized_sensor_values(
                self._temperature_model.as_float,
                self._humidity_model.as_float,
                self._soil_model.as_float,
            )
            self._write_sensor_values(values)
            self._context = context_with_sensor_values(self._context, values)
            self._status_model.set_value(
                "Fake sensors applied: "
                f"{values['temperatureC']:.1f} C, {values['humidityPct']:.1f}% RH, "
                f"{values['soilMoisturePct']:.1f}% soil"
            )
        except Exception as exc:
            self._fail(exc)

    def _set_manual_actuator(self, actuator: str, enabled: bool) -> None:
        stage = self._stage()
        previous = stage.GetEditTarget()
        try:
            runtime = self._runtime_layer(stage)
            stage.SetEditTarget(runtime)
            values = manual_actuator_values(actuator, enabled)
            if actuator == "fans":
                self._fan_speed_override = float(values["speed"])
                for index in range(1, 4):
                    self._set_command(
                        f"/World/Environment/Greenhouse/Ventilation/Fan_0{index}",
                        "command:speed", Sdf.ValueTypeNames.Float, values["speed"],
                    )
            elif actuator == "sprinklers":
                target = "/World/Environment/Greenhouse/Irrigation"
                self._set_command(
                    target, "command:sprayEnabled", Sdf.ValueTypeNames.Bool,
                    values["sprayEnabled"],
                )
                self._set_command(
                    target, "command:flow", Sdf.ValueTypeNames.Float, values["flow"]
                )
                self._set_sprinkler_effect_visible(enabled)
            elif actuator == "windows":
                self._window_ratio_target = float(values["openRatio"])
                for side in ("L", "R"):
                    self._set_command(
                        f"/World/Environment/Greenhouse/Ventilation/GH_Side_Curtain_{side}",
                        "command:openRatio", Sdf.ValueTypeNames.Float,
                        values["openRatio"],
                    )
            runtime.Save()
            state = "on" if enabled else "off"
            if actuator == "windows":
                state = "open" if enabled else "closed"
            self._status_model.set_value(f"Manual control: {actuator} {state}")
        except Exception as exc:
            self._fail(exc)
        finally:
            stage.SetEditTarget(previous)

    def _load_scenario(self, index: int) -> None:
        try:
            label, filename = SCENARIOS[index]
            context = self._load_context(filename)
            sensors = context["sensors"]
            values = normalized_sensor_values(
                sensors["temperatureC"],
                sensors["humidityPct"],
                sensors["soilMoisturePct"],
            )
            self._temperature_model.set_value(values["temperatureC"])
            self._humidity_model.set_value(values["humidityPct"])
            self._soil_model.set_value(values["soilMoisturePct"])
            self._write_sensor_values(values)
            self._context = context_with_sensor_values(context, values)
            self._proposal = None
            self._proposal_model.set_value("No Cosmos proposal yet.")
            self._status_model.set_value(f"Loaded scenario: {label}")
        except Exception as exc:
            self._fail(exc)

    def _start_analysis(self) -> None:
        if self._gantry_target is not None:
            self._status_model.set_value(
                "Wait for gantry motion to finish before capturing"
            )
            return
        if self._task and not self._task.done():
            self._status_model.set_value("A Cosmos analysis is already running")
            return
        self._task = asyncio.ensure_future(self._capture_and_analyze())

    async def _capture_and_analyze(self) -> None:
        try:
            self._activate_camera()
            output_dir = self._repo_root / "outputs/isaac_extension"
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "gantry_scan.png"
            viewport = get_active_viewport()
            capture = capture_viewport_to_file(viewport, str(image_path))
            if hasattr(capture, "wait_for_result"):
                result = capture.wait_for_result(completion_frames=30)
                if inspect.isawaitable(result):
                    await result
            elif inspect.isawaitable(capture):
                await capture
            if not image_path.exists():
                raise RuntimeError("Viewport capture did not create gantry_scan.png")

            context = context_with_inspection(
                self._context,
                self._selected_scan_lane,
                self._longitudinal_model.as_float,
            )
            image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
            agent_dir = self._repo_root / "src/agent"
            if str(agent_dir) not in sys.path:
                sys.path.insert(0, str(agent_dir))
            from cosmos_client import call_cosmos

            self._status_model.set_value("Waiting for Cosmos 3 Reasoner...")
            response, _raw = await asyncio.to_thread(call_cosmos, context, image_base64)
            response["recommendations"] = validated_recommendations(response)
            self._proposal = response
            self._proposal_model.set_value(json.dumps(response, indent=2))
            mode = "endpoint" if self._cosmos_is_configured() else "mock"
            self._status_model.set_value(f"Cosmos proposal ready ({mode}). Review before approval.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._fail(exc)

    def _cosmos_is_configured(self) -> bool:
        try:
            from cosmos_client import is_configured
            return bool(is_configured())
        except Exception:
            return False

    def _runtime_layer(self, stage):
        for layer in stage.GetLayerStack():
            if layer.identifier.replace("\\", "/").endswith("/usd/runtime/live_state.usda"):
                return layer
        raise RuntimeError("usd/runtime/live_state.usda is not in the current stage")

    def _set_command(self, prim_path: str, name: str, type_name, value: Any) -> None:
        prim = self._stage().GetPrimAtPath(prim_path)
        if not prim:
            raise RuntimeError(f"Missing command target: {prim_path}")
        attr = prim.GetAttribute(name) or prim.CreateAttribute(name, type_name, custom=True)
        attr.Set(value)

    def _set_sprinkler_effect_visible(self, enabled: bool) -> None:
        """Show or hide the deterministic sprinkler animation in session state."""
        stage = self._stage()
        available = [stage.GetPrimAtPath(p) for p in SPRINKLER_EFFECT_PATHS if stage.GetPrimAtPath(p)]
        if not available:
            raise RuntimeError("Sprinkler effects are not composed in the current stage")
        previous = stage.GetEditTarget()
        try:
            stage.SetEditTarget(stage.GetSessionLayer())
            value = sprinkler_visibility(enabled)
            for prim in available:
                attr = prim.GetAttribute("visibility")
                if not attr:
                    attr = prim.CreateAttribute("visibility", Sdf.ValueTypeNames.Token)
                attr.Set(value)
        finally:
            stage.SetEditTarget(previous)

    def _approve(self) -> None:
        if not self._proposal:
            self._status_model.set_value("Nothing to approve")
            return
        stage = self._stage()
        previous = stage.GetEditTarget()
        try:
            runtime = self._runtime_layer(stage)
            stage.SetEditTarget(runtime)
            applied = 0
            for rec in validated_recommendations(self._proposal):
                action, value = rec.get("action"), rec.get("value")
                if action == "set_fan":
                    self._fan_speed_override = float(value)
                    for index in range(1, 4):
                        self._set_command(
                            f"/World/Environment/Greenhouse/Ventilation/Fan_0{index}",
                            "command:speed", Sdf.ValueTypeNames.Float, float(value),
                        )
                    applied += 1
                elif action == "set_vent":
                    ratio = float(value) / 100.0
                    self._window_ratio_target = ratio
                    for side in ("L", "R"):
                        self._set_command(
                            f"/World/Environment/Greenhouse/Ventilation/GH_Side_Curtain_{side}",
                            "command:openRatio", Sdf.ValueTypeNames.Float, ratio,
                        )
                    applied += 1
                elif action == "set_valve":
                    flow = float(value)
                    target = "/World/Environment/Greenhouse/Irrigation"
                    self._set_command(target, "command:flow", Sdf.ValueTypeNames.Float, flow)
                    self._set_command(target, "command:sprayEnabled", Sdf.ValueTypeNames.Bool, flow > 0)
                    self._set_sprinkler_effect_visible(flow > 0)
                    applied += 1
            runtime.Save()
            self._status_model.set_value(f"Approved and wrote {applied} command group(s) to live_state.usda")
        except Exception as exc:
            self._fail(exc)
        finally:
            stage.SetEditTarget(previous)

    def _fail(self, exc: Exception) -> None:
        carb.log_error(f"[{self._ext_id}] {exc}")
        self._status_model.set_value(f"Error: {exc}")
