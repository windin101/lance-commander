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
	"paint": [2.0, 0.0], "steel": [1.5, 0.35], "galv": [1.5, 0.2], "concrete": [2.0, 0.0], "concrete_dark": [2.0, 0.0],
	"grate": [0.8, 0.3], "rust": [1.5, 0.2], "corrugated": [1.0, 0.15], "wood": [2.0, 0.0], "boards": [1.5, 0.0],
}
## decal atlas cells (tools/art/v3/bld_trim.py CELLS), for callers that lay decals out in code
const DECAL_CELLS := {"panel": 0, "diamond": 1, "id_plate": 2, "hatch": 3, "arrow": 4, "streak_a": 5, "streak_b": 6, "oil": 7,
	"soot": 8, "rust_bleed": 9, "stripe_corner": 10, "valve_tag": 11}

## --no-building-v3 (or MC2_BUILDING_V3=0) keeps the v1/v2 art for buildings alone, for before/after shots with the rest of v3 on.
static var enabled: bool = not (OS.get_cmdline_user_args().has("--no-building-v3") or OS.get_environment("MC2_BUILDING_V3") == "0")
const ALIAS := {"roofing": "corrugated", "lapwood": "wood", "silo": "paint", "hullsheet": "corrugated", "hullclean": "corrugated", "seamroof": "corrugated", "roofclean": "corrugated", "hangarroof": "corrugated", "finroof": "corrugated", "facade": "concrete", "wallconc": "concrete", "wallconc2": "concrete", "palesheet": "corrugated", "darkboards": "boards", "palewood": "boards", "darksheet": "corrugated", "wallfacade": "concrete", "sandbag": "concrete", "wallpost_s": "concrete", "wallpost_l": "concrete", "wallpost_d": "concrete"}  # model material name -> library set (see tools/art/v3/bld_*.py)
const LOD_M := 80.0  # keep in step with LOD_M in tools/art/v3/bld_tanks.py
static var _mats := {}
static var tint := Color(0.86, 0.66, 0.1)  # the faction tint where the model marks it (vertex colour R)


## The v3 model for an appearance and state ("", "_damaged", "_destroyed"), or "" (switch off, or none shipped).
static func model_path(app: String, state := "") -> String:
	if not enabled:
		return ""
	return ArtV3.model_path("objects", app + state)


## Detail levels: a glb with nodes lod0 and lod1 draws lod0 up to LOD_M from the camera and lod1 beyond. These are node
## properties, not mesh ones, so every INSTANCE needs them (dress() runs once, on a probe that is then freed: before this
## was split out, placed models drew both levels at every distance).
static func set_lods(root: Node) -> void:
	for mi in root.find_children("lod?", "MeshInstance3D", true, false):
		if mi.name == "lod0":
			(mi as GeometryInstance3D).visibility_range_end = LOD_M
		elif mi.name == "lod1":
			(mi as GeometryInstance3D).visibility_range_begin = LOD_M


## Put the library material on every surface of a model (shared mesh resources: do it once, on the probe instance).
static func dress(root: Node) -> void:
	set_lods(root)
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if mesh == null:
			continue
		for i in mesh.get_surface_count():
			var m: Material = mesh.surface_get_material(i)
			var nm := m.resource_name if m else ""
			if nm.begins_with("bv3_"):
				mesh.surface_set_material(i, material(nm.trim_prefix("bv3_")))


## Does a material name a model carries (resource_name "bv3_<name>") resolve to a library set or a special shader?
static func resolves(name: String) -> bool:
	return name in ["trim", "decal", "chain", "glass"] or ALIAS.has(name) or LIB.has(name)


static func material(name: String) -> ShaderMaterial:
	var mat: ShaderMaterial = _mats.get(name)
	if mat != null:
		return mat
	mat = ShaderMaterial.new()
	if name == "chain":
		mat.shader = load("res://shaders/building_v3_fence.gdshader")
		mat.set_shader_parameter("ar_tex", load(DIR + "chain_ar.png"))
		_mats[name] = mat
		return mat
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
			if ALIAS.has(name):
				tex = ALIAS[name]
			if name == "glass":  # dark glossy glazing: the steel set, tinted, no metal
				tex = "steel"
				mat.set_shader_parameter("base_tint", Color(0.1, 0.15, 0.2))
			if name == "interior":
				mat.set_shader_parameter("mode", 3)
				tex = "rust"
			var cfg: Array = LIB.get(tex, [2.0, 0.0])
			mat.set_shader_parameter("tile_m", float(cfg[0]))
			mat.set_shader_parameter("metal_k", 0.0 if name == "glass" else float(cfg[1]))
			mat.set_shader_parameter("contrast", 0.85 if tex == "paint" else 1.0)
			mat.set_shader_parameter("desat", 0.95 if tex == "galv" else 0.0)
			if tex == "galv":
				mat.set_shader_parameter("base_tint", Color(0.95, 0.9, 0.84))
			if tex == "corrugated":
				mat.set_shader_parameter("lined", 1.0)
				mat.set_shader_parameter("normal_depth", 0.6)
				mat.set_shader_parameter("rib_axis", 1.0)
				var pitch := {"roofing": 0.45, "roofclean": 0.45, "hangarroof": 1.53, "finroof": 0.9, "hullsheet": 0.624, "hullclean": 0.624, "seamroof": 1.53}
				var rust := {"roofing": 0.5, "roofclean": 0.08, "hangarroof": 0.05, "finroof": 0.2, "hullsheet": 0.45, "hullclean": 0.06, "seamroof": 0.18}
				mat.set_shader_parameter("rib_pitch", float(pitch.get(name, 0.3)))
				mat.set_shader_parameter("rust_k", float(rust.get(name, 0.3)))
				mat.set_shader_parameter("base_tint", Color(0.62, 0.64, 0.68) if name == "finroof" else (Color(1.4, 1.4, 1.36) if name == "hangarroof" else (Color(1.5, 1.5, 1.46) if name in ["hullclean", "roofclean"] else ( (Color(1.15, 1.13, 1.1) if name == "seamroof" else (Color(0.95, 0.93, 0.9) if pitch.has(name) else Color(1.05, 1.03, 1.0)))))))
			if name == "lapwood":
				mat.set_shader_parameter("rib_axis", 2.0)
				mat.set_shader_parameter("rib_pitch", 0.22)
				mat.set_shader_parameter("rib_dark", 0.62)
				mat.set_shader_parameter("rib_gap", 0.75)
				mat.set_shader_parameter("base_tint", Color(1.0, 0.92, 0.84))
			if name == "finroof":
				mat.set_shader_parameter("rib_dark", 0.4)
			if name == "palesheet":
				mat.set_shader_parameter("rust_k", 0.12)
				mat.set_shader_parameter("base_tint", Color(1.75, 1.78, 1.7))
			if name == "darkboards":
				mat.set_shader_parameter("base_tint", Color(0.35, 0.3, 0.26))
			if name == "palewood":
				mat.set_shader_parameter("base_tint", Color(1.5, 1.45, 1.3))
			if name == "darksheet":
				mat.set_shader_parameter("base_tint", Color(0.3, 0.3, 0.32))
			if name == "wallconc" or name == "wallpost_s":
				mat.set_shader_parameter("rib_axis", 0.0)  # smooth cast panels: the joints are geometry
				mat.set_shader_parameter("base_tint", Color(0.6, 0.64, 0.69))
				mat.set_shader_parameter("wear", 0.3)
				mat.set_shader_parameter("rust_k", 0.2)
			if name == "wallconc2" or name == "wallpost_d":
				mat.set_shader_parameter("rib_axis", 0.0)  # smooth cast panels: the joints are geometry
				mat.set_shader_parameter("base_tint", Color(0.74, 0.68, 0.55))
				mat.set_shader_parameter("wear", 0.3)
			if name == "wallfacade" or name == "wallpost_l":
				mat.set_shader_parameter("rib_axis", 0.0)  # smooth cast panels: the joints are geometry
				mat.set_shader_parameter("base_tint", Color(0.55, 0.66, 0.56))
				mat.set_shader_parameter("wear", 0.3)
				mat.set_shader_parameter("rust_k", 0.2)
			if name == "wallpost_s":  # post blocks stand out against the body: near white, the originals' bright capped blocks
				mat.set_shader_parameter("base_tint", Color(0.92, 0.96, 1.02))
			elif name == "wallpost_l":
				mat.set_shader_parameter("base_tint", Color(0.84, 0.98, 0.86))
			elif name == "wallpost_d":
				mat.set_shader_parameter("base_tint", Color(1.1, 1.03, 0.86))
			if name == "facade":
				mat.set_shader_parameter("base_tint", Color(1.02, 0.93, 0.8))
				mat.set_shader_parameter("rust_k", 0.18)
				mat.set_shader_parameter("rust_col", Color(0.3, 0.22, 0.15))
			if name == "sandbag":
				mat.set_shader_parameter("base_tint", Color(1.05, 1.0, 0.82))
				mat.set_shader_parameter("rib_axis", 0.0)
			if name == "silo":
				mat.set_shader_parameter("base_tint", Color(0.92, 0.84, 0.72))
				mat.set_shader_parameter("rust_k", 0.35)
			if tex == "paint" and name != "silo":
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
