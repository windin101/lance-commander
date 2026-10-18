class_name RtsCamera
extends Camera3D
## Orbit camera around a ground focus point: WASD / edge pan, Q/E rotate,
## mouse wheel zoom, middle-drag rotate.

@export var focus := Vector3.ZERO
@export var distance := 260.0
@export var yaw_deg := 0.0  # 0 = looking north
@export var pitch_deg := 50.0
@export var min_distance := 60.0
@export var max_distance := 900.0
@export var pan_speed := 1.2  # map widths per second at max zoom, scaled by distance
@export var bounds_half := 1280.0

var height_at: Callable  # optional: Vector2 -> float, keeps the focus on the ground


func _ready() -> void:
	_apply()


func _process(delta: float) -> void:
	var move := Vector2.ZERO
	if Input.is_physical_key_pressed(KEY_W): move.y += 1
	if Input.is_physical_key_pressed(KEY_S): move.y -= 1
	if Input.is_physical_key_pressed(KEY_A): move.x -= 1
	if Input.is_physical_key_pressed(KEY_D): move.x += 1
	if Input.is_physical_key_pressed(KEY_Q): yaw_deg -= 90.0 * delta
	if Input.is_physical_key_pressed(KEY_E): yaw_deg += 90.0 * delta
	if move != Vector2.ZERO:
		var yaw := deg_to_rad(yaw_deg)
		var fwd := Vector3(sin(yaw), 0, -cos(yaw))
		var right := Vector3(cos(yaw), 0, sin(yaw))
		focus += (fwd * move.y + right * move.x).normalized() * distance * pan_speed * delta
		focus.x = clampf(focus.x, -bounds_half, bounds_half)
		focus.z = clampf(focus.z, -bounds_half, bounds_half)
	_apply()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = maxf(min_distance, distance * 0.9)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = minf(max_distance, distance * 1.1)
	elif event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_MIDDLE):
		yaw_deg += event.relative.x * 0.3
		pitch_deg = clampf(pitch_deg + event.relative.y * 0.2, 20.0, 85.0)


func _apply() -> void:
	if height_at.is_valid():
		focus.y = height_at.call(Vector2(focus.x, -focus.z))
	var yaw := deg_to_rad(yaw_deg)
	var pitch := deg_to_rad(pitch_deg)
	var back := Vector3(-sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	global_position = focus + back * distance
	look_at(focus, Vector3.UP)
