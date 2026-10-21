class_name IntroFlyby
extends Node
## The mission's opening camera flyby in "movie mode" (HUD hidden, input off),
## from data/brains/<mission>.json script.flyby (mc2_01.abl stages 1-8).
## Each leg eases the camera focus to a point while turning to a yaw/pitch.
## Esc / Space skips to the end (the original's ForceMovieToEnd). Emits finished.

signal finished

const WORLD_UNIT_M := 0.2

var view: Node
var cfg: Dictionary
var base_yaw := 0.0  # the original's StartRotation; legs' yaw_offset is relative to it
var legs: Array = []
var _leg := -1
var _t := 0.0
var _from_focus := Vector3.ZERO
var _from_yaw := 0.0
var _from_pitch := 0.0
var _done := false
var skipped := false  # the player pressed Esc/Space: the mission script's movie is skipped too


func setup(mission_view: Node, flyby_cfg: Dictionary, start_rotation: float) -> void:
	view = mission_view
	cfg = flyby_cfg
	base_yaw = start_rotation
	legs = cfg.get("legs", [])
	var s: Array = cfg.get("start", [])
	if legs.is_empty() or s.is_empty() or OS.get_cmdline_user_args().has("--skip-intro"):
		_finish.call_deferred()
		return
	view.hud.visible = false
	view.input.set_process_unhandled_input(false)
	var p := Vector2(s[0], s[1]) * WORLD_UNIT_M
	view.camera.focus = Vector3(p.x, 0, -p.y)
	view.camera.yaw_deg = RtsCamera.from_original_yaw(base_yaw + float(legs[0].get("yaw_offset", 0.0)))
	view.camera.pitch_deg = float(legs[0].get("pitch", 35.0))
	_next_leg()


func _next_leg() -> void:
	_leg += 1
	if _leg >= legs.size():
		_finish()
		return
	_t = 0.0
	_from_focus = view.camera.focus
	_from_yaw = view.camera.yaw_deg
	_from_pitch = view.camera.pitch_deg


func _process(delta: float) -> void:
	if _done or _leg < 0 or _leg >= legs.size():
		return
	var leg: Dictionary = legs[_leg]
	_t += delta
	var to: Vector2 = Vector2(leg["to"][0], leg["to"][1]) * WORLD_UNIT_M
	var m := _ease(_t / maxf(float(leg.get("move_time", 1.0)), 0.01))
	var r := _ease(_t / maxf(float(leg.get("turn_time", 1.0)), 0.01))
	var target_focus := Vector3(to.x, 0, -to.y)
	view.camera.focus = _from_focus.lerp(target_focus, m)
	var target_yaw := RtsCamera.from_original_yaw(base_yaw + float(leg.get("yaw_offset", 0.0)))
	view.camera.yaw_deg = rad_to_deg(lerp_angle(deg_to_rad(_from_yaw), deg_to_rad(target_yaw), r))
	view.camera.pitch_deg = lerpf(_from_pitch, float(leg.get("pitch", 35.0)), r)
	if _t >= float(leg.get("hold", leg.get("move_time", 1.0))):
		_next_leg()


func _unhandled_input(event: InputEvent) -> void:
	if _done:
		return
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ESCAPE, KEY_SPACE]:
		var last: Dictionary = legs[legs.size() - 1]
		var to: Vector2 = Vector2(last["to"][0], last["to"][1]) * WORLD_UNIT_M
		view.camera.focus = Vector3(to.x, 0, -to.y)
		view.camera.yaw_deg = RtsCamera.from_original_yaw(base_yaw + float(last.get("yaw_offset", 0.0)))
		view.camera.pitch_deg = float(last.get("pitch", 35.0))
		get_viewport().set_input_as_handled()
		skipped = true
		_finish()


func is_running() -> bool:
	return not _done


static func _ease(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func _finish() -> void:
	if _done:
		return
	_done = true
	if view.hud:
		view.hud.visible = true
	view.input.set_process_unhandled_input(true)
	finished.emit()
