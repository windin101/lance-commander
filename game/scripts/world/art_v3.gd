class_name ArtV3
extends RefCounted
## Switch for the HD rework v3 (Pipeline A, 2026-10-24: tools/art/v3/v3_mech.py), models staged under
## res://assets/v3/<mechs|vehicles>/<name>.glb with baked textures <name>_{albedo,orm,normal,ids,camo}.png.
## On by default since 2026-10-25 (Lee). Off with the user argument --no-art-v3, the environment variable
## MC2_ART_V3=0, or [art] v3=false in user://dev.cfg; --art-v3 / MC2_ART_V3=1 force it on. With it on, MechView and
## MechStage take a v3 model where one exists (before v2 and v1), paint it with res://shaders/unit_v3.gdshader, and
## the pilot scenes (Mech Bay, Mech Lab, missions) get the v3 lighting: sun shadows, sky ambient and reflections,
## reflection probes, SSAO, the AgX tonemapper and TAA.

static var enabled: bool = _detect()
static var _mats := {}


static func _detect() -> bool:
	var args := OS.get_cmdline_user_args()
	if args.has("--no-art-v3") or OS.get_environment("MC2_ART_V3") == "0":
		return false
	if args.has("--art-v3") or OS.get_environment("MC2_ART_V3") == "1":
		return true
	var cfg := ConfigFile.new()
	if cfg.load("user://dev.cfg") == OK:
		return bool(cfg.get_value("art", "v3", true))
	return true  # the default since 2026-10-25 (Lee); units without a v3 model keep their v1/v2 art


## The staged v3 model for folder/name, or "" (switch off, or no v3 model).
static func model_path(folder: String, name: String) -> String:
	if not enabled:
		return ""
	var p := "res://assets/v3/%s/%s.glb" % [folder, name]
	return p if ResourceLoader.exists(p) else ""


## A scheme colour as the v3 shader takes it (linear): the scheme's own colour, kept inside the PBR range for paint
## (no pure saturated or near-white enamel), so AgX shows it as painted.
static func paint_colour(c: Color) -> Color:
	var v := Color.from_hsv(c.h, minf(c.s, 0.92), clampf(c.v, 0.04, 0.88))
	return v.srgb_to_linear()


## Paint every mesh under root with the v3 shader and a scheme (PaintScheme dictionary).
static func apply(root: Node, name: String, scheme: Dictionary, folder: String = "mechs") -> ShaderMaterial:
	var key := "%s/%s|%s" % [folder, name, str(scheme)]
	var mat: ShaderMaterial = _mats.get(key)
	if mat == null:
		mat = ShaderMaterial.new()
		mat.shader = load("res://shaders/unit_v3.gdshader")
		var dir := "res://assets/v3/%s/%s" % [folder, name]
		for k in ["albedo", "orm", "normal", "ids", "camo"]:
			var p := "%s_%s.png" % [dir, k]
			if ResourceLoader.exists(p):
				var t: Texture2D = load(p)
				mat.set_shader_parameter("%s_tex" % k, t)
				if k == "ids":
					mat.set_shader_parameter("ids_lin_tex", t)
		if ResourceLoader.exists("res://assets/v3/shared/detail_normal.png"):
			mat.set_shader_parameter("detail_tex", load("res://assets/v3/shared/detail_normal.png"))
		set_scheme(mat, scheme)
		mat.set_shader_parameter("dust", MechPaint.env_dust)
		mat.set_shader_parameter("snow", MechPaint.env_snow)
		mat.set_shader_parameter("dust_colour", MechPaint.env_dust_colour)
		_mats[key] = mat
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_override = mat
	return mat


## Scheme uniforms: per region base/hl1/hl2/steel, piping/stripe/band, the camouflage pattern. A mission's own
## colours (mode "mask") paint the body in the base colour, the plates in highlight 2 and the trims in highlight 1.
static func set_scheme(mat: ShaderMaterial, scheme: Dictionary) -> void:
	var col := {"base": paint_colour(Color(String(scheme.get("base", "#808080")))),
		"hl1": paint_colour(Color(String(scheme.get("hl1", "#808080")))),
		"hl2": paint_colour(Color(String(scheme.get("hl2", "#808080"))))}
	var regions: Dictionary = scheme.get("regions", {})
	var mask_mode := regions.is_empty() or String(scheme.get("mode", "")) == "mask"
	if mask_mode:
		regions = {"plates": "hl2", "weapons": "steel"}
	var rc := PackedVector3Array()
	var rs := PackedFloat32Array()
	var rcamo := PackedFloat32Array()
	for r in PaintScheme.REGIONS:
		var v := String(regions.get(r, "base"))
		var c: Color = col.get(v, col["base"])
		rc.append(Vector3(c.r, c.g, c.b))
		rs.append(1.0 if v == "steel" else 0.0)
		rcamo.append(1.0 if v == "base" else 0.0)
	mat.set_shader_parameter("region_colour", rc)
	mat.set_shader_parameter("region_steel", rs)
	mat.set_shader_parameter("region_camo", rcamo)
	var trims := {"piping": scheme.get("piping"), "stripe": scheme.get("stripe"), "band": scheme.get("band")}
	if mask_mode:
		trims = {"piping": null, "stripe": null, "band": "hl1"}
	for k in trims:
		var v = trims[k]
		var on := v != null and String(v) != ""
		mat.set_shader_parameter("%s_on" % k, 1.0 if on else 0.0)
		if on:
			var s := String(v)
			var c: Color = col.get(s, paint_colour(Color(s)) if s.begins_with("#") else col["hl1"])
			mat.set_shader_parameter("%s_colour" % k, c.linear_to_srgb())  # source_color uniforms take sRGB
	mat.set_shader_parameter("pattern", maxi(0, PaintScheme.PATTERNS.find(String(scheme.get("pattern", "plain")))))


static func set_environment(dust: float, snow: float, colour: Color) -> void:
	for m in _mats.values():
		(m as ShaderMaterial).set_shader_parameter("dust", dust)
		(m as ShaderMaterial).set_shader_parameter("snow", snow)
		(m as ShaderMaterial).set_shader_parameter("dust_colour", colour)


# --- lighting for the pilot scenes -------------------------------------------------------------------------------

## The v3 look-dev environment on an existing Environment: AgX, sky ambient and reflections, SSAO. Mission fog and
## glow stay as they are.
static func dress_environment(env: Environment, sky_energy := 1.0) -> void:
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_white = 6.0
	env.tonemap_exposure = 1.0
	if env.sky != null:
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
		env.ambient_light_sky_contribution = 0.85
		env.ambient_light_energy = sky_energy
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 1.6
	env.ssao_light_affect = 0.1


## Temporal anti-aliasing on a viewport (the main defence against specular shimmer on panel edges and chips).
static func dress_viewport(vp: Viewport) -> void:
	vp.use_taa = true
	vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED


## A sky for the studio (Mech Bay / Mech Lab) so metal has something to reflect: a dim hangar-like procedural sky.
static func studio_sky() -> Sky:
	var sky := Sky.new()
	var m := ProceduralSkyMaterial.new()
	m.sky_top_color = Color(0.32, 0.36, 0.42)
	m.sky_horizon_color = Color(0.55, 0.57, 0.6)
	m.ground_horizon_color = Color(0.3, 0.29, 0.28)
	m.ground_bottom_color = Color(0.1, 0.1, 0.1)
	m.sky_energy_multiplier = 0.9
	sky.sky_material = m
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	return sky
