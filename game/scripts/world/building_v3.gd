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
const ALIAS := {"roofing": "corrugated", "lapwood": "wood", "silo": "paint", "hullsheet": "corrugated", "hullclean": "corrugated", "seamroof": "corrugated", "roofclean": "corrugated", "hangarroof": "corrugated", "finroof": "corrugated", "facade": "concrete", "wallconc": "concrete", "wallconc2": "concrete", "palesheet": "corrugated", "darkboards": "boards", "palewood": "boards", "darksheet": "corrugated", "wallfacade": "concrete", "sandbag": "concrete", "wallpost_s": "concrete", "wallpost_l": "concrete", "wallpost_d": "concrete", "brick": "concrete", "palepaint": "paint", "tealpaint": "paint", "pipegreen": "paint", "slate": "paint", "palecorr": "corrugated", "safetyyellow": "paint", "machgrey": "paint", "bandgreen": "paint", "bandorange": "paint", "tankgrey": "paint", "roofdark": "paint", "lightcorr": "corrugated", "brickcity": "concrete", "greybrick": "concrete", "whitecity": "concrete", "facadeblue": "concrete", "facadegreen": "concrete", "tealwall": "paint", "tinroof": "corrugated", "wglass": "steel", "camogreen": "paint", "tanwall": "paint", "steinerwhite": "paint", "creamwall": "paint", "bluetrim": "paint", "lightroof": "paint", "scorchblack": "concrete", "glassgreen": "steel", "glassblue": "steel", "glasslight": "steel", "bedgreen": "paint", "planting": "paint", "tealpanel": "paint", "tanroof": "corrugated", "stonewall": "concrete", "redframe": "paint", "flagcloth": "paint", "canvas": "paint", "netgreen": "paint"}  # model material name -> library set (see tools/art/v3/bld_*.py)
const TINTS := {"brick": Color(0.46, 0.3, 0.27), "palepaint": Color(0.7, 0.74, 0.76), "tealpaint": Color(0.5, 0.7, 0.74), "pipegreen": Color(0.66, 0.8, 0.74),
	"slate": Color(0.045, 0.06, 0.07), "palecorr": Color(0.52, 0.56, 0.58), "safetyyellow": Color(1.02, 0.84, 0.26), "machgrey": Color(0.46, 0.54, 0.6),
	"bandgreen": Color(0.32, 0.62, 0.4), "bandorange": Color(0.95, 0.5, 0.2), "tankgrey": Color(0.52, 0.57, 0.57), "roofdark": Color(0.045, 0.055, 0.065), "lightcorr": Color(0.86, 0.91, 0.94),
	"brickcity": Color(0.66, 0.4, 0.36), "greybrick": Color(0.58, 0.61, 0.63), "whitecity": Color(0.82, 0.86, 0.88), "facadeblue": Color(0.5, 0.6, 0.72), "facadegreen": Color(0.46, 0.6, 0.57),
	"tealwall": Color(0.36, 0.52, 0.56), "tinroof": Color(0.5, 0.52, 0.5),
	"camogreen": Color(0.46, 0.58, 0.34), "tanwall": Color(0.72, 0.64, 0.5), "steinerwhite": Color(1.3, 1.33, 1.36),
	"creamwall": Color(1.1, 1.07, 0.98), "bluetrim": Color(0.3, 0.45, 0.66), "lightroof": Color(0.88, 0.92, 0.95), "scorchblack": Color(0.05, 0.045, 0.04), "glassgreen": Color(0.12, 0.34, 0.26), "glassblue": Color(0.4, 0.55, 0.68), "glasslight": Color(0.4, 0.68, 0.46), "bedgreen": Color(0.24, 0.5, 0.2), "planting": Color(0.3, 0.42, 0.26), "tealpanel": Color(0.22, 0.5, 0.46), "tanroof": Color(0.92, 0.84, 0.56), "stonewall": Color(0.7, 0.76, 0.66), "redframe": Color(0.62, 0.2, 0.16),
	"flagcloth": Color(0.8, 0.12, 0.1), "canvas": Color(0.42, 0.62, 0.5), "netgreen": Color(0.2, 0.3, 0.22)}  # industrial family (bld_industry.py): per-name tint on the shared set  # model material name -> library set (see tools/art/v3/bld_*.py)
## The mission snow value (unit_weather.json) is tuned for the units. A building roof faces straight up, so the full value turned every flat
## roof near-white on mc2_18 (snow 0.45, a dark dusk map whose ground is bare): buildings take this share of it.
const SNOW_K := 0.06
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
	for mi in root.find_children("lod*", "MeshInstance3D", true, false):  # lod0 / lod1, or lod0_<part> / lod1_<part> in a model with moving parts (bld_turrets.py)
		if mi.name.begins_with("lod0"):
			(mi as GeometryInstance3D).visibility_range_end = LOD_M
		elif mi.name.begins_with("lod1"):
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
	return name in ["trim", "decal", "chain", "glass", "interior", "wglass"] or ALIAS.has(name) or LIB.has(name)


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
			if name == "wglass":  # facade window glass: near black and matte, so windows read dark at the RTS camera; lit at night
				tex = "steel"
				mat.set_shader_parameter("base_tint", Color(0.03, 0.04, 0.05))
				mat.set_shader_parameter("rough_add", 0.55)
			if name == "glass":  # dark glossy glazing: the steel set, tinted, no metal
				tex = "steel"
				mat.set_shader_parameter("base_tint", Color(0.1, 0.15, 0.2))
			if name == "interior":
				mat.set_shader_parameter("mode", 3)
				tex = "rust"
			var cfg: Array = LIB.get(tex, [2.0, 0.0])
			mat.set_shader_parameter("tile_m", float(cfg[0]))
			mat.set_shader_parameter("metal_k", 0.0 if (name == "glass" or name == "wglass") else float(cfg[1]))
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
		mat.set_shader_parameter("snow", MechPaint.env_snow * SNOW_K)
		mat.set_shader_parameter("dust_colour", MechPaint.env_dust_colour)
	if night:
		mat.set_shader_parameter("night_lift", NIGHT_LIFT)
	mat.set_shader_parameter("map_gain", map_gain)
	if TINTS.has(name):  # last, so the set's own defaults (paint's warm grey) don't win
		mat.set_shader_parameter("base_tint", TINTS[name])
		mat.set_shader_parameter("contrast", 0.5)  # calm the set's speckle: wear is placed, not sprayed (style guide 1.2)
		if name == "slate" or name == "roofdark":
			mat.set_shader_parameter("rough_add", 0.6)  # roofs do not mirror a low sun
		mat.set_shader_parameter("rib_axis", 1.0 if (name == "palecorr" or name == "lightcorr" or name == "tinroof" or name == "tanroof") else 0.0)
		if name == "palecorr" or name == "lightcorr" or name == "tinroof" or name == "tanroof":
			mat.set_shader_parameter("rib_pitch", 0.3)
	_mats[name] = mat
	return mat


## Mission dust and snow on every v3 building surface (called from ArtV3.set_environment).
static func set_environment(dust: float, snow: float, colour: Color) -> void:
	for k in _mats:
		if k == "decal":
			continue
		var m: ShaderMaterial = _mats[k]
		m.set_shader_parameter("dust", dust)
		m.set_shader_parameter("snow", snow * SNOW_K)
		m.set_shader_parameter("dust_colour", colour)


## A whole-model burn on top of the vertex burn (0..1): the wreck states bake theirs, this is for hit flashes.
## Night: the window glass (material wglass) lights up, dim amber on a hash of the window cell (style guide 10: dim amber windows at night).
static var night := false

const NIGHT_LIFT := 1.9
## Per-mission albedo gain for v3 buildings (measured: v3 against the original on building crops, tools in bld/ind/dim_check.sh). Day maps stay 1.
const MAP_GAIN := {"mc2_19": 1.45, "mc2_23": 1.3, "mc2_05": 0.72, "mc2_18": 0.85, "mc2_21": 0.78}
static var map_gain := 1.0


static func set_map_gain(mission: String) -> void:
	map_gain = float(MAP_GAIN.get(mission, 1.0))
	for k in _mats:
		(_mats[k] as ShaderMaterial).set_shader_parameter("map_gain", map_gain)



static func set_night(on: bool) -> void:
	night = on
	for k in _mats:
		(_mats[k] as ShaderMaterial).set_shader_parameter("night_lift", NIGHT_LIFT if on else 1.0)
	var m: ShaderMaterial = material("wglass")
	m.set_shader_parameter("emit_k", 0.9 if on else 0.0)


static func set_scorch(amount: float) -> void:
	for k in _mats:
		(_mats[k] as ShaderMaterial).set_shader_parameter("scorch", amount)
