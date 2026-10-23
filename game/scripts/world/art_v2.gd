class_name ArtV2
extends RefCounted
## Dev switch for the HD rework (v2) models staged under res://assets/v2/<mechs|vehicles|objects>/<name>.glb
## (tools/art/hd_v2.py). Off by default, so the installed HD models stay what players see until Lee approves.
## On with the user argument --art-v2, the environment variable MC2_ART_V2=1, or [art] v2=true in
## user://dev.cfg; --no-art-v2 forces it off. With it on, every loader (MechView, MechStage, ObjectsView) takes a
## v2 model where one exists and falls back to the usual order otherwise.

static var enabled: bool = _detect()


static func _detect() -> bool:
	var args := OS.get_cmdline_user_args()
	if args.has("--no-art-v2"):
		return false
	if args.has("--art-v2") or OS.get_environment("MC2_ART_V2") == "1":
		return true
	var cfg := ConfigFile.new()
	if cfg.load("user://dev.cfg") == OK:
		return bool(cfg.get_value("art", "v2", false))
	return false


## The staged v2 model for folder/name, or "" (switch off, or no v2 model).
static func model_path(folder: String, name: String) -> String:
	if not enabled:
		return ""
	var p := "res://assets/v2/%s/%s.glb" % [folder, name]
	return p if ResourceLoader.exists(p) else ""


## Surface types of a v2 building (tools/art/hd_v2_building.py: material "v2_<type>") -> the tiling set in
## res://assets/v2/shared/ and its shader settings.
const SURFACES := {
	"sheet": {"metallic": 0.18}, "panel": {}, "concrete": {}, "trim": {"metallic": 0.12}, "door": {"metallic": 0.1},
	"glass": {"is_glass": 1.0},
}
static var _surface_mats := {}


## Swap a v2 building's "v2_<type>" materials for the building shader, on the mesh resources themselves (every
## instance shares them, as ObjectsView's probe relies on). app names its AO bake (<app>_ao.png).
static func dress_object(root: Node, app: String) -> void:
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if mesh == null:
			continue
		for i in mesh.get_surface_count():
			var m: Material = mesh.surface_get_material(i)
			if m == null or m is ShaderMaterial or not String(m.resource_name).begins_with("v2_"):
				continue
			var ty := String(m.resource_name).trim_prefix("v2_")
			var key := "%s|%s" % [app, ty]
			var sm: ShaderMaterial = _surface_mats.get(key)
			if sm == null:
				sm = ShaderMaterial.new()
				sm.shader = load("res://shaders/building_hd.gdshader")
				var set_ := "res://assets/v2/shared/%s" % ty
				if ResourceLoader.exists(set_ + "_albedo.png"):
					sm.set_shader_parameter("albedo_tex", load(set_ + "_albedo.png"))
					sm.set_shader_parameter("normal_tex", load(set_ + "_normal.png"))
				var ao := "res://assets/v2/objects/%s_ao.png" % app
				if ResourceLoader.exists(ao):
					sm.set_shader_parameter("ao_tex", load(ao))
				sm.set_shader_parameter("grunge_tex", load("res://assets/v2/shared/grunge.png"))
				for k in SURFACES.get(ty, {}):
					sm.set_shader_parameter(k, SURFACES[ty][k])
				sm.set_shader_parameter("dust", MechPaint.env_dust)
				sm.set_shader_parameter("snow", MechPaint.env_snow)
				sm.set_shader_parameter("dust_colour", MechPaint.env_dust_colour)
				_surface_mats[key] = sm
			mesh.surface_set_material(i, sm)
