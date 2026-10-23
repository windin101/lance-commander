class_name MechPaint
extends RefCounted
## Team paint schemes, as Mech3DAppearance::setPaintScheme (mech3d.cpp:1613).
## Pure red, green or blue mask pixels become the scheme colour scaled by
## 1 - (1 - v/256)^2; any other pixel keeps its painted colour.
## Missions pass (HighlightColor1, HighlightColor2, BaseColor) for (red, green, blue).

static var _cache := {}
## Environment layer of the v2 unit shader (HD rework 2026-10-23): dust and snow cover, 0..1, set per mission.
static var env_dust := 0.0
static var env_snow := 0.0


## ARGB int from a mission FIT (may be negative) -> Color.
static func argb(value: int) -> Color:
	var v := value & 0xFFFFFFFF
	return Color8((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


static func shade(channel: int) -> float:
	var x := 1.0 - float(channel) / 256.0
	return 1.0 - x * x


static func recolor(mask: Image, red: Color, green: Color, blue: Color) -> Image:
	var img := mask.duplicate() as Image
	img.convert(Image.FORMAT_RGBA8)
	var data := img.get_data()
	for i in range(0, data.size(), 4):
		var r := data[i]
		var g := data[i + 1]
		var b := data[i + 2]
		var c: Color
		var k: float
		if g == 0 and b == 0:
			c = red
			k = shade(r)
		elif r == 0 and b == 0:
			c = green
			k = shade(g)
		elif r == 0 and g == 0:
			c = blue
			k = shade(b)
		else:
			continue
		# The original truncates to unsigned char.
		data[i] = int(c.r8 * k)
		data[i + 1] = int(c.g8 * k)
		data[i + 2] = int(c.b8 * k)
		data[i + 3] = 255
	return Image.create_from_data(img.get_width(), img.get_height(), img.has_mipmaps(), Image.FORMAT_RGBA8, data)


static func load_mask(model_name: String, folder: String = "mechs") -> Image:
	var bytes := FileAccess.get_file_as_bytes("res://assets/%s/%s_paint.bin" % [folder, model_name])
	var img := Image.new()
	if bytes.is_empty() or img.load_png_from_buffer(bytes) != OK:
		return null
	return img


static func _first_material(root: Node) -> StandardMaterial3D:
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if mesh and mesh.get_surface_count() > 0 and mesh.surface_get_material(0) is StandardMaterial3D:
			return mesh.surface_get_material(0)
	return null


## Recolour every mesh under root with one material using the painted texture.
## A "<model>_v2" name (ArtV2 models) gets the v2 unit shader instead (apply_v2).
static func apply(root: Node, model_name: String, red: Color, green: Color, blue: Color, folder: String = "mechs") -> void:
	if model_name.ends_with("_v2"):
		apply_v2(root, model_name.trim_suffix("_v2"), red, green, blue, folder)
		return
	var key := "%s/%s|%s|%s|%s" % [folder, model_name, red.to_html(), green.to_html(), blue.to_html()]
	var mat: StandardMaterial3D = _cache.get(key)
	if mat == null:
		var mask := load_mask(model_name, folder)
		if mask == null:
			return
		var painted := recolor(mask, red, green, blue)
		painted.generate_mipmaps()
		mat = StandardMaterial3D.new()
		mat.albedo_texture = ImageTexture.create_from_image(painted)
		mat.metallic = 0.35
		mat.roughness = 0.55
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		# HD models carry baked normal and AO maps: keep them under the team paint.
		var src := _first_material(root)
		if src:
			if src.normal_enabled and src.normal_texture:
				mat.normal_enabled = true
				mat.normal_texture = src.normal_texture
				mat.normal_scale = 1.0
			if src.ao_enabled and src.ao_texture:
				mat.ao_enabled = true
				mat.ao_texture = src.ao_texture
				mat.ao_light_affect = 0.6
		_cache[key] = mat
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_override = mat


# --- v2 (HD rework, 2026-10-23) ---------------------------------------------------------------------------

static var _v2_mats: Array[ShaderMaterial] = []
static var env_dust_colour := Color(0.56, 0.5, 0.4)


## A team colour as the v2 shader takes it: a little desaturated and below full brightness, so a scheme's pure
## green or red reads as paint under PBR light rather than as an emissive sticker.
static func _paint_colour(c: Color) -> Color:
	# paint response: a mission's pure saturated colours (#00FF00, #FFFF00) read as enamel, not as light
	# light colours lose most under the bay's key and rim lights: #9a9a9a must read as mid-grey paint, not white
	var lv := smoothstep(0.35, 0.65, c.v)
	var out := Color.from_hsv(c.h, minf(c.s, 0.85) * (0.82 if c.s > 0.7 else 0.92), minf(c.v, 0.86) * 0.9 * lerpf(1.0, 0.78, lv))
	return out


## Paint a model with a scheme (PaintScheme): the v2 shader for a "<model>_v2" name, else the v1 recolour of the
## team mask with the scheme's plain colours (v1 palette UVs can't take a pattern).
static func apply_scheme(root: Node, model_name: String, scheme: Dictionary, folder: String = "mechs") -> void:
	var c := PaintScheme.plain_colours(scheme)
	if not model_name.ends_with("_v2"):
		apply(root, model_name, c[0], c[1], c[2], folder)
		return
	apply_v2(root, model_name.trim_suffix("_v2"), c[0], c[1], c[2], folder, scheme)


## The v2 unit shader (res://shaders/unit_hd.gdshader) with this model's mask, detail and normal maps
## (res://assets/v2/<folder>/<name>_{mask,detail,normal}.png) and the team colours: red = HighlightColor1,
## green = HighlightColor2, blue = BaseColor, as the original's mask channels.
static func apply_v2(root: Node, name: String, red: Color, green: Color, blue: Color, folder: String = "mechs",
		scheme: Dictionary = {}) -> void:
	var key := "v2/%s/%s|%s|%s|%s|%s" % [folder, name, red.to_html(), green.to_html(), blue.to_html(), str(scheme)]
	var mat: ShaderMaterial = _cache.get(key)
	if mat == null:
		var dir := "res://assets/v2/%s/%s" % [folder, name]
		mat = ShaderMaterial.new()
		mat.shader = load("res://shaders/unit_hd.gdshader")
		for k in ["mask", "detail", "normal", "zones", "camo"]:
			var p := "%s_%s.png" % [dir, k]
			if ResourceLoader.exists(p):
				mat.set_shader_parameter("%s_tex" % k, load(p))
				if k == "zones":
					mat.set_shader_parameter("zones_id_tex", load(p))
				if k == "mask":
					mat.set_shader_parameter("mask_id_tex", load(p))
		_set_scheme(mat, scheme, red, green, blue)
		mat.set_shader_parameter("grunge_tex", load("res://assets/v2/shared/grunge.png"))
		mat.set_shader_parameter("base_colour", _paint_colour(blue))
		mat.set_shader_parameter("hl1_colour", _paint_colour(red))
		mat.set_shader_parameter("hl2_colour", _paint_colour(green))
		var rig_path := "%s.rig.json" % dir
		if FileAccess.file_exists(rig_path):
			var rig: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(rig_path))
			mat.set_shader_parameter("height_m", float(rig.get("height_m", 9.0)))
			if rig.has("rest_min"):
				var rm: Array = rig["rest_min"]; var re: Array = rig["rest_extent"]
				mat.set_shader_parameter("rest_min", Vector3(rm[0], rm[1], rm[2]))
				mat.set_shader_parameter("rest_extent", Vector3(re[0], re[1], re[2]))
			for k in ["wear", "grime", "burns", "grunge_scale"]:
				if rig.has(k):
					mat.set_shader_parameter(k, float(rig[k]))
		_set_env(mat)
		_cache[key] = mat
		_v2_mats.append(mat)
	var seed := float(absi(hash(root.name)) % 997) / 9.97
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_override = mat
		(mi as MeshInstance3D).set_instance_shader_parameter("unit_seed", seed)


## Scheme uniforms: regions (mode "regions", the default for a scheme with "regions") or the team mask.
static func _set_scheme(mat: ShaderMaterial, scheme: Dictionary, red: Color, green: Color, blue: Color) -> void:
	var regions: Dictionary = scheme.get("regions", {})
	if regions.is_empty() or String(scheme.get("mode", "")) == "mask":
		mat.set_shader_parameter("scheme_mode", 0)
		if scheme.has("decal"):
			mat.set_shader_parameter("decal_colour", Color(String(scheme["decal"])))
		return
	var col := {"base": _paint_colour(blue), "hl1": _paint_colour(red), "hl2": _paint_colour(green)}
	var rc := PackedVector3Array(); var rs := PackedFloat32Array(); var rcamo := PackedFloat32Array()
	for r in PaintScheme.REGIONS:
		var v := String(regions.get(r, "base"))
		var c: Color = (col.get(v, col["base"]) as Color).srgb_to_linear()  # a vec3 array uniform takes no source_color hint
		rc.append(Vector3(c.r, c.g, c.b))
		rs.append(1.0 if v == "steel" else 0.0)
		rcamo.append(1.0 if v == "base" else 0.0)
	mat.set_shader_parameter("scheme_mode", 1)
	mat.set_shader_parameter("region_colour", rc)
	mat.set_shader_parameter("region_steel", rs)
	mat.set_shader_parameter("region_camo", rcamo)
	for k in ["piping", "stripe", "band"]:
		var v = scheme.get(k)
		var on := v != null and String(v) != ""
		mat.set_shader_parameter("%s_on" % k, 1.0 if on else 0.0)
		if on:
			var c: Color = col.get(String(v), Color(String(v)) if String(v).begins_with("#") else col["hl1"])
			mat.set_shader_parameter("%s_colour" % k, c)
	mat.set_shader_parameter("decal_colour", Color(String(scheme.get("decal", "#d8d4c8"))))
	mat.set_shader_parameter("insignia_on", 1.0 if bool(scheme.get("insignia", false)) else 0.0)
	mat.set_shader_parameter("pattern", maxi(0, PaintScheme.PATTERNS.find(String(scheme.get("pattern", "plain")))))


static func _set_env(mat: ShaderMaterial) -> void:
	mat.set_shader_parameter("dust", env_dust)
	mat.set_shader_parameter("snow", env_snow)
	mat.set_shader_parameter("dust_colour", env_dust_colour)


## The mission's dust and snow layer on every v2 unit (game/data/unit_weather.json, tools/art/unit_weather.py).
static func set_environment_for(mission: String) -> void:
	var path := "res://data/unit_weather.json"
	var w: Dictionary = {}
	if FileAccess.file_exists(path):
		w = JSON.parse_string(FileAccess.get_file_as_string(path)).get(mission, {})
	set_environment(float(w.get("dust", 0.25)), float(w.get("snow", 0.0)), Color(String(w.get("dust_colour", "#8f8066"))))


static func set_environment(dust: float, snow: float, colour: Color) -> void:
	env_dust = dust
	env_snow = snow
	env_dust_colour = colour
	for m in _v2_mats:
		_set_env(m)
