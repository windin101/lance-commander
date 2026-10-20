class_name CameraCompass
extends MeshInstance3D
## The original's compass: a translucent ground decal at the camera focus, fixed to world north,
## drawn over terrain and units (gamecam.cpp:160-196, 557-596; the "compass" building appearance,
## Data/TGL/Compass.ase: a 354.5 wu = 70.9 m square textured with A_Compass.tga, whose own alpha
## tops out near 30%). Hidden in movie mode and for the first frames of a mission (turn > 3).
## Backslash toggles it (toggleCompass, missiongui.cpp:276; gamecam.h:124).

const SIZE_M := 70.9
const SHOW_AFTER_S := 0.1  # the original waits for turn > 3

var camera: RtsCamera
var hidden_when: Callable  # optional: -> bool (cinematic running)
var enabled := true  # the original kept this in the registry (CompassStatus); on by default here
var _age := 0.0


func setup(cam: RtsCamera, hide_if: Callable = Callable()) -> void:
	camera = cam
	hidden_when = hide_if
	var quad := PlaneMesh.new()  # faces +Y; UV v=0 (image top, the north arrow) at -Z = north
	quad.size = Vector2(SIZE_M, SIZE_M)
	mesh = quad
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.no_depth_test = true  # "Force this to zBuffer in front of everything" (gamecam.cpp:168)
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.disable_fog = true
	mat.albedo_texture = load("res://assets/ui/compass.png")
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	mat.render_priority = Material.RENDER_PRIORITY_MAX
	material_override = mat
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	visible = false


func _process(delta: float) -> void:
	_age += delta
	if camera == null:
		return
	global_position = camera.focus + Vector3(0, 0.3, 0)
	rotation = Vector3.ZERO  # fixed to world north (setObjectParameters(pos, 0.0), gamecam.cpp:588)
	visible = enabled and _age >= SHOW_AFTER_S and not (hidden_when.is_valid() and hidden_when.call())


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_BACKSLASH:
		if hidden_when.is_valid() and hidden_when.call():
			return
		enabled = not enabled
		get_viewport().set_input_as_handled()
