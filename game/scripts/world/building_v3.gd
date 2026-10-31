class_name BuildingV3
extends RefCounted
## v3 buildings (LANCE-21, tools/art/v3/bld_*.py): procedural models under res://assets/v3/objects/<app>[_damaged|_destroyed].glb
## whose surfaces are named bv3_<material>. Every surface takes a ShaderMaterial from the shared library
## (res://assets/v3/shared/buildings/, ambientCG CC0 plus the project trim sheet and decal atlas), shared by every building,
## so a model carries no textures of its own. Loaded by ObjectsView behind ArtV3; a building without a v3 model keeps its
## v1/v2 art.

const DIR := "res://assets/v3/shared/buildings/"
## material -> [tile metres, metalness scale]; mirrors materials.json (tools/art/v3/bld_materials.py)
const LIB := {
	"paint": [2.0, 0.0], "steel": [1.5, 1.0], "galv": [1.5, 1.0], "concrete": [2.0, 0.0], "concrete_dark": [2.0, 0.0],
	"grate": [0.8, 1.0], "rust": [1.5, 0.6], "corrugated": [1.0, 1.0],
}
## decal atlas cells (tools/art/v3/bld_trim.py CELLS), for callers that lay decals out in code
const DECAL_CELLS := {"panel": 0, "diamond": 1, "id_plate": 2, "hatch": 3, "arrow": 4, "streak_a": 5, "streak_b": 6, "oil": 7,
	"soot": 8, "rust_bleed": 9, "stripe_corner": 10, "valve_tag": 11}

## --no-building-v3 (or MC2_BUILDING_V3=0) keeps the v1/v2 art for buildings alone, for before/after shots with the rest of v3 on.
static var enabled: bool = not (OS.get_cmdline_user_args().has("--no-building-v3") or OS.get_environment("MC2_BUILDING_V3") == "0")
const LOD_M := 80.0  # keep in step with LOD_M in tools/art/v3/bld_tanks.py
static var _mats := {}
static var tint := Color(0.86, 0.66, 0.1)  # the faction tint where the model marks it (vertex colour R)


## The v3 model for an appearance and state ("", "_damaged", "_destroyed"), or "" (switch off, or none shipped).
static func model_path(app: String, state := "") -> String:
	if not enabled:
		return ""
	return ArtV3.model_path("objects", app + state)


## Put the library material on every surface of a model (shared mesh resources: do it once, on the probe instance).
static func dress(root: Node) -> void:
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if mesh == null:
			continue
		# detail levels: a glb with nodes lod0 and lod1 draws lod0 up to LOD_M from the camera and lod1 beyond
		if mi.name == "lod0":
			(mi as GeometryInstance3D).visibility_range_end = LOD_M
		elif mi.name == "lod1":
			(mi as GeometryInstance3D).visibility_range_begin = LOD_M
		for i in mesh.get_surface_count():
			var m: Material = mesh.surface_get_material(i)
			var nm := m.resource_name if m else ""
			if nm.begins_with("bv3_"):
				mesh.surface_set_material(i, material(nm.trim_prefix("bv3_")))


static func material(name: String) -> ShaderMaterial:
	var mat: ShaderMaterial = _mats.get(name)
	if mat != null:
		return mat
	mat = ShaderMaterial.new()
	if name == "decal":
		mat.shader = load("res://shaders/building_v3_decal.gdshader")
		mat.set_shader_parameter("ar_tex", load(DIR + "decals_ar.png"))
		mat.render_priority = 1
	else:
		mat.shader = load("res://shaders/building_v3.gdshader")
		var tex := name
		if name == "trim":
			mat.set_shader_parameter("mode", 1)
			mat.set_shader_parameter("ar_tex", load(DIR + "trim_ar.png"))
			mat.set_shader_parameter("nm_tex", load(DIR + "trim_nm.png"))
		else:
			if name == "interior":
				mat.set_shader_parameter("mode", 3)
				tex = "rust"
			var cfg: Array = LIB.get(tex, [2.0, 0.0])
			mat.set_shader_parameter("tile_m", float(cfg[0]))
			mat.set_shader_parameter("metal_k", float(cfg[1]))
			mat.set_shader_parameter("contrast", 0.85 if tex == "paint" else 1.0)
			mat.set_shader_parameter("desat", 0.75 if tex == "galv" else 0.0)
			if tex == "paint":
				mat.set_shader_parameter("base_tint", Color(0.9, 0.88, 0.84))
			mat.set_shader_parameter("ar_tex", load(DIR + tex + "_ar.webp"))
			mat.set_shader_parameter("nm_tex", load(DIR + tex + "_nm.webp"))
		if ResourceLoader.exists("res://assets/v2/shared/grunge.png"):
			mat.set_shader_parameter("grunge_tex", load("res://assets/v2/shared/grunge.png"))
		mat.set_shader_parameter("tint", tint)
		mat.set_shader_parameter("dust", MechPaint.env_dust)
		mat.set_shader_parameter("snow", MechPaint.env_snow)
		mat.set_shader_parameter("dust_colour", MechPaint.env_dust_colour)
	_mats[name] = mat
	return mat


## Mission dust and snow on every v3 building surface (called from ArtV3.set_environment).
static func set_environment(dust: float, snow: float, colour: Color) -> void:
	for k in _mats:
		if k == "decal":
			continue
		var m: ShaderMaterial = _mats[k]
		m.set_shader_parameter("dust", dust)
		m.set_shader_parameter("snow", snow)
		m.set_shader_parameter("dust_colour", colour)


## A whole-model burn on top of the vertex burn (0..1): the wreck states bake theirs, this is for hit flashes.
static func set_scorch(amount: float) -> void:
	for k in _mats:
		(_mats[k] as ShaderMaterial).set_shader_parameter("scorch", amount)
