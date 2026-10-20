class_name RtsCamera
extends Camera3D
## Orbit camera around a ground focus point, matching the original's mission camera
## (MCLib/Camera.cpp, Code/gamecam.cpp, Code/missiongui.cpp; MC2 world unit = 0.2 m).
## Arrows pan; Shift+Left/Right rotate in 11.25 deg snaps; Shift+Up/Down tilt (Up = steeper);
## + / = / numpad+ zoom in, - / numpad- zoom out; Home resets the view; the mouse at a screen
## edge scrolls; hold left Alt and move the mouse to rotate (x) and tilt (y), or middle-drag;
## the wheel zooms. Pan and zoom speeds scale with the zoom the way the original's did.
## The projection (40 deg horizontal FOV, Camera.cpp:499) is set by the mission view, not here,
## so the dev model viewer keeps its own.

const DEFAULT_PITCH := 35.0  # allNormal tilt (Camera.cpp:113)
const DEFAULT_DISTANCE := 240.0  # AltitudeDefault 1200 wu (Camera.cpp:122)
const MIN_PITCH := 10.0
const MAX_PITCH := 88.0
const ZOOM_REF_M := 111.8  # distance where the scale factor is 1 (fully zoomed in)
const PAN_SPEED := 66.5  # m/s at scale 1: scrollInc / getScaleFactor (missiongui.cpp:2525-2552)
const ZOOM_SPEED := 200.0  # m/s held, times the scale factor (missiongui.cpp:2554-2565)
const TILT_SPEED := 38.0  # deg/s held, divided by the scale factor (missiongui.cpp:2602-2615)
const ROT_SNAP := 11.25  # rotationInc: rotation moves in whole snaps (missiongui.cpp:2579-2600)
const ROT_SPEED := 337.5  # deg/s held: one snap per frame at the original's 30 fps
const MOUSE_DEG_PER_PX := 1.125  # Alt-rotate / tilt by mouse
const WHEEL_STEP := 33.0  # m per wheel notch, times the scale factor
const EDGE_PX := 5.0  # screenScroll* zone at each edge (missionscrn.fit:9-12, missiongui.cpp:3312-3327)
const EDGE_MARGIN := 204.0  # the focus stays this far inside the map edge
const HEIGHT_SNAP_GAP := 30.0  # ground-height jumps above this ease instead of snapping
const JUMP_M := 50.0  # a focus move this big in one frame is a jump (minimap, script): snap the height
const CLEARANCE := 40.0  # ELEVATION_BUFFER 125 + 75 wu above the ground (Camera.cpp:2087-2091)
const CLEARANCE_STEP := 0.25  # ANGLE_UP_INC: pitch raised until the camera clears (Camera.cpp:1943, 2104)

@export var focus := Vector3.ZERO
@export var distance := DEFAULT_DISTANCE
@export var yaw_deg := 0.0  # 0 = looking north
@export var pitch_deg := DEFAULT_PITCH
@export var min_distance := 112.0
@export var bounds_half := 1280.0
@export var edge_scroll := true
@export var limits := true  # pitch / zoom / bounds limits; dev views (model viewer, --cam) turn them off

var home_yaw := 0.0  # Home returns here: the mission's [Cameras] StartRotation
var height_at: Callable  # optional: Vector2 -> float, keeps the focus on the ground
var input_blocked: Callable  # optional: -> bool, true while a cinematic owns the camera
var follow_pos: Callable  # optional: SimUnit -> Vector3, where a followed unit is drawn
var following: SimUnit = null  # re-centred on every frame until any pan
var view_pitch := DEFAULT_PITCH  # the pitch actually used, after terrain clearance
var _focus_h := NAN
var _last_xz := Vector2(INF, INF)
var _rot_dir := 0
var _rot_acc := 0.0
var _alt_rotate := false  # left Alt held: mouse motion rotates and tilts
var _mouse_in := false  # the pointer is over the window (no edge scroll otherwise)


func _ready() -> void:
	_apply()


func _process(delta: float) -> void:
	if not _blocked():
		var shift := Input.is_key_pressed(KEY_SHIFT)
		var keys := Vector2.ZERO
		var lr := int(Input.is_physical_key_pressed(KEY_RIGHT)) - int(Input.is_physical_key_pressed(KEY_LEFT))
		var ud := int(Input.is_physical_key_pressed(KEY_UP)) - int(Input.is_physical_key_pressed(KEY_DOWN))
		if not shift:
			keys = Vector2(lr, ud)
		var zoom := int(Input.is_physical_key_pressed(KEY_EQUAL) or Input.is_physical_key_pressed(KEY_KP_ADD)) \
			- int(Input.is_physical_key_pressed(KEY_MINUS) or Input.is_physical_key_pressed(KEY_KP_SUBTRACT))
		tick(delta, keys + _edge_move(), -lr if shift else 0, ud if shift else 0, zoom)
	else:
		_rot_dir = 0
	if following:
		if following.has_method("is_destroyed") and following.is_destroyed():
			following = null
		else:
			var p: Vector3 = follow_pos.call(following) if follow_pos.is_valid() \
				else Vector3(following.position.x, 0, -following.position.y)
			focus.x = p.x
			focus.z = p.z
	_apply(delta)


## One frame of camera control. pan: x right / y forward, from keys and edge scroll (diagonals
## are not normalised, as in the original); rot: +1 = yaw left; tilt: +1 = steeper; zoom: +1 = in.
func tick(delta: float, pan: Vector2, rot: int, tilt: int, zoom: int) -> void:
	var s := scale_factor()
	if pan != Vector2.ZERO:
		following = null
		var yaw := deg_to_rad(yaw_deg)
		var fwd := Vector3(sin(yaw), 0, -cos(yaw))
		var right := Vector3(cos(yaw), 0, sin(yaw))
		focus += (fwd * pan.y + right * pan.x) * PAN_SPEED / s * delta
	_rotate_step(rot, delta)
	if tilt != 0:
		pitch_deg += tilt * TILT_SPEED / s * delta
	if zoom != 0:
		distance -= zoom * ZOOM_SPEED * s * delta


## Held rotation: a tap is one snap, holding repeats at ROT_SPEED (missiongui.cpp:2579-2600).
func _rotate_step(rot: int, delta: float) -> void:
	if rot == 0:
		_rot_dir = 0
		return
	if rot != _rot_dir:
		_rot_dir = rot
		_rot_acc = 0.0
		yaw_deg -= rot * ROT_SNAP
		return
	_rot_acc += ROT_SPEED * delta
	while _rot_acc >= ROT_SNAP:
		_rot_acc -= ROT_SNAP
		yaw_deg -= rot * ROT_SNAP


## The original's zoom scale: 1 fully in, falling as the camera pulls back (getScaleFactor).
func scale_factor() -> float:
	return maxf(0.05, 1.0 - (distance - ZOOM_REF_M) / max_distance_for(pitch_deg))


## Furthest zoom at a tilt: 299.4 m at 10 deg rising to 319.4 m at 88 deg (~306 m at 35).
static func max_distance_for(pitch: float) -> float:
	return 299.4 + 20.0 * (pitch - MIN_PITCH) / (MAX_PITCH - MIN_PITCH)


## Edge-scroll direction for a mouse position: 5 px zone per edge, x right / y forward.
static func edge_dir(mouse: Vector2, screen: Vector2) -> Vector2:
	if not Rect2(Vector2.ZERO, screen).has_point(mouse):
		return Vector2.ZERO
	var d := Vector2.ZERO
	if mouse.x < EDGE_PX:
		d.x = -1
	elif mouse.x >= screen.x - EDGE_PX:
		d.x = 1
	if mouse.y < EDGE_PX:
		d.y = 1
	elif mouse.y >= screen.y - EDGE_PX:
		d.y = -1
	return d


func _edge_move() -> Vector2:
	if not edge_scroll or _alt_rotate or not _mouse_in or DisplayServer.get_name() == "headless":
		return Vector2.ZERO
	var vp := get_viewport()
	return edge_dir(vp.get_mouse_position(), vp.get_visible_rect().size)


## Home: the default view at the mission's start rotation (cameraNormal, missiongui.cpp:206).
func reset_view() -> void:
	pitch_deg = DEFAULT_PITCH
	distance = DEFAULT_DISTANCE
	yaw_deg = home_yaw


## Re-centre on a unit every frame until the player pans (GameCamera::setTarget, missiongui.cpp:3307-3311).
func follow(unit: SimUnit) -> void:
	following = unit


## Jump the focus to a map point (minimap click); stops following and respects the map bounds.
func pan_to(p: Vector2) -> void:
	following = null
	focus.x = p.x
	focus.z = -p.y
	_apply()


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.keycode == KEY_ALT and event.location != KEY_LOCATION_RIGHT:
		_alt_rotate = event.pressed
	elif event is InputEventMouseMotion:
		_mouse_in = true
		if _blocked():
			return
		if _alt_rotate or (event.button_mask & MOUSE_BUTTON_MASK_MIDDLE):
			yaw_deg += event.relative.x * MOUSE_DEG_PER_PX
			pitch_deg += event.relative.y * MOUSE_DEG_PER_PX  # mouse down = steeper


func _unhandled_input(event: InputEvent) -> void:
	if _blocked():
		return
	if event is InputEventMouseButton and event.pressed:
		# Forward = zoom in (our choice; the original's wheel sign is unproven).
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance -= WHEEL_STEP * scale_factor()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance += WHEEL_STEP * scale_factor()
	elif event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_HOME:
		reset_view()
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_MOUSE_EXIT:
		_mouse_in = false
	elif what == NOTIFICATION_WM_MOUSE_ENTER:
		_mouse_in = true
	elif what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_alt_rotate = false  # Alt-Tab never sends the release


func _blocked() -> bool:
	return input_blocked.is_valid() and input_blocked.call()


## Place the camera. delta > 0 lets the focus ease over big ground-height jumps; 0 snaps.
func _apply(delta: float = 0.0) -> void:
	if limits:
		pitch_deg = clampf(pitch_deg, MIN_PITCH, MAX_PITCH)
		distance = clampf(distance, min_distance, max_distance_for(pitch_deg))
		var lim := maxf(bounds_half - EDGE_MARGIN, 0.0)
		focus.x = clampf(focus.x, -lim, lim)
		focus.z = clampf(focus.z, -lim, lim)
	if height_at.is_valid():
		var xz := Vector2(focus.x, -focus.z)
		var g: float = height_at.call(xz)
		var jumped := xz.distance_to(_last_xz) > JUMP_M
		_last_xz = xz
		if is_nan(_focus_h) or delta <= 0.0 or jumped or absf(g - _focus_h) <= HEIGHT_SNAP_GAP:
			_focus_h = g
		else:
			_focus_h += (g - _focus_h) * 0.5 * delta
		focus.y = _focus_h
	view_pitch = pitch_deg
	var yaw := deg_to_rad(yaw_deg)
	var pos := _orbit(yaw, view_pitch)
	# Keep the eye above the ground behind it: tilt up in small steps, for this frame only.
	if limits and height_at.is_valid():
		while view_pitch < MAX_PITCH and pos.y < float(height_at.call(Vector2(pos.x, -pos.z))) + CLEARANCE:
			view_pitch += CLEARANCE_STEP
			pos = _orbit(yaw, view_pitch)
	global_position = pos
	look_at(focus, Vector3.UP)


func _orbit(yaw: float, pitch_d: float) -> Vector3:
	var pitch := deg_to_rad(pitch_d)
	return focus + Vector3(-sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * distance
