class_name TerrainView
extends Node3D
## Visible terrain and water for a SimMap. Godot axes: X east, Y up, -Z north,
## so a sim position (x, y) is Vector3(x, height, -y).
## The colour map covers the whole map side (vertices x 128 world units), as
## the original's TerrainColorMap does.

var map: SimMap
## The mission FIT's [Water] block (AlphaShallow/Middle/Deep as packed ARGB, AlphaDepth), set before build().
var water_fit: Dictionary = {}
## [Terrain] WaterDetailTilingFactor.
var water_detail_tiling := 45.0


static func to_3d(pos: Vector2, height: float) -> Vector3:
	return Vector3(pos.x, height, -pos.y)


func build(sim_map: SimMap, texture_dir: String) -> void:
	map = sim_map
	for child in get_children():
		child.queue_free()
	var ground := MeshInstance3D.new()
	ground.name = "Ground"
	ground.mesh = _ground_mesh()
	var mat := _v3_material(texture_dir.get_file()) if TerrainV3.enabled else null
	var v3 := mat != null
	if not v3:
		mat = ShaderMaterial.new()
		mat.shader = load("res://shaders/terrain.gdshader")
		mat.set_shader_parameter("colour_map", load(texture_dir.path_join("burnin.jpg")))
		var detail_path := texture_dir.path_join("detail.tga")
		if ResourceLoader.exists(detail_path):
			mat.set_shader_parameter("detail_map", load(detail_path))
		mat.set_shader_parameter("rock_noise", _noise_texture(false, 256, 0.02))
		_ground_detail(mat)
	_overlay_layer(mat)
	ground.material_override = mat
	# The colour map already carries the hills' own shading and cast shadows (burn-in): the ground must
	# not shadow itself again. It still receives the shadows of everything standing on it.
	# The v3 ground is lit (no burn-in on screen), so its hills cast their own shadows.
	# v3: the coarse 25.6 m mesh's own cast shadows came out as stair-stepped black bands; the recovered relief map
	# (relief.py, from the burn-in's smooth shading) carries the hills' dark sides instead, so the ground casts none
	ground.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if OS.get_cmdline_user_args().has("--no-terrain-draw"):  # dev: perf isolation of the terrain pass
		ground.visible = false
	ground.layers = 1 | 2  # layer 2: ground marks (DecalsView) project only onto the terrain
	add_child(ground)
	var skirt := MeshInstance3D.new()
	skirt.name = "Skirt"
	skirt.mesh = _skirt_mesh()
	skirt.material_override = mat
	skirt.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	skirt.layers = 1 | 2
	skirt.visible = ground.visible
	add_child(skirt)
	if v3 and not OS.get_cmdline_user_args().has("--no-terrain-dress"):
		var dress := TerrainDressV3.new()
		dress.name = "DressV3"
		add_child(dress)
		dress.build(map, texture_dir.get_file(), _v3_layers)
	if map.water_level_m > -100.0:
		var w := _water(texture_dir)
		add_child(w)
		var ws := MeshInstance3D.new()
		ws.name = "WaterSkirt"
		ws.mesh = _water_skirt_mesh()
		ws.material_override = w.material_override
		ws.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(ws)


static func _noise_texture(as_normal_map: bool, px: int, frequency: float) -> NoiseTexture2D:
	var t := NoiseTexture2D.new()
	var noise := FastNoiseLite.new()
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	noise.fractal_octaves = 5
	noise.frequency = frequency
	t.noise = noise
	t.width = px
	t.height = px
	t.seamless = true
	t.as_normal_map = as_normal_map
	t.bump_strength = 6.0
	t.generate_mipmaps = true
	return t


func _ground_mesh() -> ArrayMesh:
	var n := map.vertices_per_side
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var tiling := float(map.meta.get("detail_tiling", 30.0))
	for row in n:
		for col in n:
			var pos := Vector2(-map.half_m + col * map.vertex_m, map.half_m - row * map.vertex_m)
			st.set_uv(Vector2(float(col) / n, float(row) / n))
			st.set_uv2(Vector2(float(col) / n, float(row) / n) * tiling)
			st.add_vertex(to_3d(pos, map.vertex_height(row, col)))
	for row in n - 1:
		for col in n - 1:
			var i := row * n + col
			st.add_index(i)
			st.add_index(i + 1)
			st.add_index(i + n)
			st.add_index(i + 1)
			st.add_index(i + n + 1)
			st.add_index(i + n)
	st.generate_normals()
	st.generate_tangents()
	return st.commit()


## Water plane at the mission's water level. Opacity per vertex as the original set it (quad.cpp:2069-2105):
## AlphaShallow where the ground is within AlphaDepth of the surface, AlphaDeep below 3 x AlphaDepth, and
## AlphaMiddle between, from the mission FIT (packed ARGB: the top byte is the alpha). Dry vertices are
## clear, so the shoreline fades out.
func _water(texture_dir: String) -> MeshInstance3D:
	var n := map.vertices_per_side
	var tiling := float(map.meta.get("water_tiling", 48.0))
	var a_depth := float(water_fit.get("AlphaDepth", map.meta.get("water_alpha_depth", 15.0))) * map.meters_per_wu
	var a_sh := _alpha_byte(water_fit.get("AlphaShallow", 2097152000)) / 255.0
	var a_mid := _alpha_byte(water_fit.get("AlphaMiddle", -1358954496)) / 255.0
	var a_deep := _alpha_byte(water_fit.get("AlphaDeep", -16777216)) / 255.0
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for row in n:
		for col in n:
			var pos := Vector2(-map.half_m + col * map.vertex_m, map.half_m - row * map.vertex_m)
			var depth := map.water_level_m - map.vertex_height(row, col)
			var alpha := 0.0
			if depth > 0.0:
				alpha = a_sh if depth <= a_depth else (a_deep if depth >= 3.0 * a_depth else a_mid)
			st.set_color(Color(1, 1, 1, alpha))
			st.set_uv(Vector2(float(col) / n, float(row) / n))
			st.add_vertex(to_3d(pos, map.water_level_m))
	for row in n - 1:
		for col in n - 1:
			var i := row * n + col
			st.add_index(i)
			st.add_index(i + 1)
			st.add_index(i + n)
			st.add_index(i + 1)
			st.add_index(i + n + 1)
			st.add_index(i + n)
	st.generate_normals()
	var water := MeshInstance3D.new()
	water.name = "Water"
	water.mesh = st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/water.gdshader")
	mat.set_shader_parameter("water_tex", load(texture_dir.path_join("water.tga")))
	mat.set_shader_parameter("wave_noise", _noise_texture(true, 256, 0.04))
	mat.set_shader_parameter("tiling", tiling)
	mat.set_shader_parameter("detail_tiling", water_detail_tiling)
	var sparkle := texture_dir.path_join("water_detail.png")
	if ResourceLoader.exists(sparkle):
		mat.set_shader_parameter("detail_atlas", load(sparkle))
		mat.set_shader_parameter("detail_strength", 1.0)
	# Mission [Water] Frequency / Ampliture (world units) -> a gentle swell in metres.
	var amp := float(map.meta.get("water_amplitude", 3.0)) * map.meters_per_wu
	mat.set_shader_parameter("swell_height", clampf(amp, 0.1, 1.5))
	water.material_override = mat
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return water


## Alpha of a packed ARGB value from the FIT (stored as a signed 32-bit integer).
static func _alpha_byte(v) -> float:
	return float((int(v) >> 24) & 255)



## The road / runway / bridge overlay tiles and the cement pads the original drew over the colour map
## (quad.cpp:248-301): one 64 px overlay tile per terrain quad from terrain.json "overlay_texture" (runtime
## slots, decoded by tools/art/env_textures.py into assets/terrain/overlays.json), and cement where the vertex
## terrain type is a cement type. Both go to the shader as small per-map index textures.
func _overlay_layer(mat: ShaderMaterial) -> void:
	var stem := "res://assets/terrain/overlays_hd"  # 4x upscaled tiles (tools/art/upscale_textures.py --tiles)
	var ext := ".webp" if ResourceLoader.exists(stem + ".webp") else ".png"
	if not ResourceLoader.exists(stem + ext) or OS.get_cmdline_user_args().has("--no-hd"):
		ext = ".png"
		stem = "res://assets/terrain/overlays"
	var info_path := stem + ".json"
	if not FileAccess.file_exists(info_path) or not ResourceLoader.exists(stem + ext):
		return
	var info: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(info_path))
	var slots: Dictionary = info["slots"]
	var cement: Dictionary = info["cement_types"]
	var n := map.vertices_per_side
	var ov: Array = map.meta.get("overlay_texture", [])
	var tt: Array = map.meta.get("terrain_type", [])
	var idx := Image.create(n, n, false, Image.FORMAT_RGF)  # R: overlay atlas cell + 1, G: cement atlas cell + 1
	var weight := Image.create(n, n, false, Image.FORMAT_RF)  # 1 at cement vertices (filtered for soft edges)
	var used := 0
	for i in mini(n * n, ov.size()):
		var col := i % n
		var row := i / n
		var cell := float(slots.get(str(int(ov[i])), -1)) + 1.0
		var c_cell := 0.0
		var w := 0.0
		if i < tt.size() and cement.has(str(int(tt[i]))):
			c_cell = float(cement[str(int(tt[i]))]) + 1.0
			w = 1.0
		if cell > 0.0:
			used += 1
		idx.set_pixel(col, row, Color(cell, c_cell, 0.0))
		weight.set_pixel(col, row, Color(w, 0.0, 0.0))
	mat.set_shader_parameter("overlay_atlas", load(stem + ext))
	mat.set_shader_parameter("overlay_index", ImageTexture.create_from_image(idx))
	var mk_path := "res://assets/terrain/v3/markings.json"
	if TerrainV3.enabled and FileAccess.file_exists(mk_path) and not OS.get_cmdline_user_args().has("--old-paving"):
		# T7b: vector markings (tools/art/terrain/markings.py), a compact atlas indexed by its own cell per quad
		var mk: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(mk_path))
		var remap: Dictionary = mk["remap"]
		var idx3 := Image.create(n, n, false, Image.FORMAT_RF)
		for i in mini(n * n, ov.size()):
			var cell := int(slots.get(str(int(ov[i])), -1))
			idx3.set_pixel(i % n, i / n, Color(float(remap.get(str(cell), -1)) + 1.0, 0, 0))
		mat.set_shader_parameter("markings", load("res://assets/terrain/v3/markings.png"))
		mat.set_shader_parameter("markings_index", ImageTexture.create_from_image(idx3))
		mat.set_shader_parameter("mk_cols", float(mk["cols"]))
		mat.set_shader_parameter("mk_tile", float(mk["tile"]))
		mat.set_shader_parameter("mk_pad", float(mk["pad"]))
		mat.set_shader_parameter("mk_spread", float(mk["spread_m"]))
	mat.set_shader_parameter("cement_weight", ImageTexture.create_from_image(weight))
	mat.set_shader_parameter("atlas_cols", float(info["cols"]))
	mat.set_shader_parameter("atlas_tile", float(info["tile"]))
	mat.set_shader_parameter("atlas_pad", float(info["pad"]))
	mat.set_shader_parameter("vertices_per_side", float(n))



## Ground detail layers (step 2): the five CC0 classes as two texture arrays (grain, normals). The shader picks
## the class from the colour map's own colour and adds only grain and relief up close.
const DETAIL_CLASSES := ["grass", "dirt", "rock", "sand", "snow"]


func _ground_detail(mat: ShaderMaterial) -> void:
	var grain: Array[Image] = []
	var normals: Array[Image] = []
	for c in DETAIL_CLASSES:
		var lp := "res://assets/terrain/detail/%s_l.png" % c
		var np := "res://assets/terrain/detail/%s_n.jpg" % c
		if not ResourceLoader.exists(lp) or not ResourceLoader.exists(np):
			return
		grain.append(_layer_image(load(lp), Image.FORMAT_RGB8))
		normals.append(_layer_image(load(np), Image.FORMAT_RGB8))
	var ga := Texture2DArray.new()
	ga.create_from_images(grain)
	var na := Texture2DArray.new()
	na.create_from_images(normals)
	mat.set_shader_parameter("detail_l", ga)
	mat.set_shader_parameter("detail_n", na)
	mat.set_shader_parameter("ground_detail", 1.0)
	mat.set_shader_parameter("ground_relief", 0.7)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--terrain-debug="):
			mat.set_shader_parameter("debug_view", int(a.split("=")[1]))
	print("ground detail: %d layers, %dx%d" % [ga.get_layers(), ga.get_width(), ga.get_height()])


static func _layer_image(tex: Texture2D, format: Image.Format) -> Image:
	var im := tex.get_image()
	if im.is_compressed():
		im.decompress()
	im.clear_mipmaps()
	im.convert(format)
	im.generate_mipmaps()
	return im


## Edge skirt (step 2): the world used to stop at the map edge, a cliff into the sky. A ring of ground runs
## SKIRT_M outward from the border vertices, falling gently to below the water line, sharing the terrain
## material: its UVs fall outside 0..1, so the colour map's edge pixels stretch outward, and the haze hides
## the far rim. It is scenery only: the sim and the camera stay inside the map.
const SKIRT_M := 3000.0


func _skirt_mesh() -> ArrayMesh:
	var n := map.vertices_per_side
	var border: Array[Vector2i] = []
	for c in n: border.append(Vector2i(0, c))
	for r in range(1, n): border.append(Vector2i(r, n - 1))
	for c in range(n - 2, -1, -1): border.append(Vector2i(n - 1, c))
	for r in range(n - 2, 0, -1): border.append(Vector2i(r, 0))
	var low := minf(map.water_level_m, 0.0) - 30.0
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var span := map.vertex_m * (n - 1)
	for b in border:
		var pos := Vector2(-map.half_m + b.y * map.vertex_m, map.half_m - b.x * map.vertex_m)
		var uv := Vector2(float(b.y) / n, float(b.x) / n)
		var h := map.vertex_height(b.x, b.y)
		var dir := pos.normalized()
		for k in 3:  # border, 30 % out at the edge height, the far rim below the water
			var t: float = [0.0, 0.3, 1.0][k]
			var p: Vector2 = pos + dir * SKIRT_M * t
			var uvk: Vector2 = uv + Vector2(dir.x, -dir.y) * (SKIRT_M * t / span)
			st.set_uv(uvk)
			st.set_uv2(uvk * float(map.meta.get("detail_tiling", 30.0)))
			st.add_vertex(to_3d(p, h if k < 2 else lerpf(h, low, 1.0)))
	var m := border.size()
	for i in m:
		var j := (i + 1) % m
		for k in 2:
			var a := i * 3 + k
			var b2 := j * 3 + k
			st.add_index(a); st.add_index(a + 1); st.add_index(b2)  # same winding as the ground mesh
			st.add_index(b2); st.add_index(a + 1); st.add_index(b2 + 1)
	st.generate_normals()
	return st.commit()


## The sea continues past the map edge (with the edge skirt): a ring at the water level, opaque where the
## border is under water, faded out where it is dry land, so coasts stay coasts.
func _water_skirt_mesh() -> ArrayMesh:
	var n := map.vertices_per_side
	var border: Array[Vector2i] = []
	for c in n: border.append(Vector2i(0, c))
	for r in range(1, n): border.append(Vector2i(r, n - 1))
	for c in range(n - 2, -1, -1): border.append(Vector2i(n - 1, c))
	for r in range(n - 2, 0, -1): border.append(Vector2i(r, 0))
	var a_deep := _alpha_byte(water_fit.get("AlphaDeep", -16777216)) / 255.0
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for b in border:
		var pos := Vector2(-map.half_m + b.y * map.vertex_m, map.half_m - b.x * map.vertex_m)
		var wet := map.water_level_m - map.vertex_height(b.x, b.y) > 0.0
		var dir := pos.normalized()
		for k in 2:
			var p: Vector2 = pos + dir * SKIRT_M * float(k)
			st.set_color(Color(1, 1, 1, a_deep if wet else 0.0))
			var uvk: Vector2 = Vector2(float(b.y) / n, float(b.x) / n) + Vector2(dir.x, -dir.y) * (SKIRT_M * float(k) / (map.vertex_m * (n - 1)))
			st.set_uv(uvk)
			st.add_vertex(to_3d(p, map.water_level_m))
	var m := border.size()
	for i in m:
		var j := (i + 1) % m
		var a := i * 2
		var b2 := j * 2
		st.add_index(a); st.add_index(a + 1); st.add_index(b2)
		st.add_index(b2); st.add_index(a + 1); st.add_index(b2 + 1)
	st.generate_normals()
	return st.commit()


## Terrain v3 (T3, LAN-68; TerrainV3.enabled): the lit PBR ground from res://assets/terrain/v3/<map>/ and its
## palette arrays (tools/art/terrain/terrain_pack.py). null when the map has no v3 data (the v1 ground is used).
const V3_WET := 7
var _v3_layers: Array = []


func _v3_material(map_name: String) -> ShaderMaterial:
	var dir := "res://assets/terrain/v3/%s" % map_name
	if not FileAccess.file_exists(dir.path_join("terrain_v3.json")):
		return null
	var info: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("terrain_v3.json")))
	var pal := String(info["palette"])
	var pdir := "res://assets/terrain/v3/palettes"
	var pinfo: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(pdir.path_join(pal + ".json")))
	_v3_layers = pinfo["layers"]
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain_v3.gdshader")
	var splat: Texture2D = load(dir.path_join("splat.png"))
	mat.set_shader_parameter("splat", splat)
	mat.set_shader_parameter("splat_px", float(splat.get_width()))
	mat.set_shader_parameter("tint", load(dir.path_join("tint.png")))
	mat.set_shader_parameter("layers_ah", load(pdir.path_join(pal + "_ah.webp")))
	mat.set_shader_parameter("layers_nr", load(pdir.path_join(pal + "_nr.webp")))
	mat.set_shader_parameter("variation", _noise_texture(false, 256, 0.05))
	mat.set_shader_parameter("map_side_m", map.vertex_m * map.vertices_per_side)
	var tiles := PackedFloat32Array()
	var means := PackedVector3Array()
	var rough := PackedFloat32Array()
	var albs := PackedFloat32Array()
	var i := 0
	for l in pinfo["layers"]:
		tiles.append(float(l["tile_m"]))
		var c: Array = l["mean_albedo"]
		var lin := Color(float(c[0]) / 255.0, float(c[1]) / 255.0, float(c[2]) / 255.0).srgb_to_linear()
		means.append(Vector3(lin.r, lin.g, lin.b))
		rough.append(0.55 if i == V3_WET else 1.0)   # wet: smoother and darker
		albs.append(0.75 if i == V3_WET else 1.0)
		i += 1
	mat.set_shader_parameter("tile_m", tiles)
	mat.set_shader_parameter("albedo_gain", float(info.get("albedo_gain", 1.0)))
	if info.has("shadow_fill"):   # low-ambient maps: a floor of the ground's own colour in cast shadow (palettes.json maps.<m>.shadow_fill)
		mat.set_shader_parameter("shadow_fill", float(info["shadow_fill"]))
	if info.has("tint_strength"):
		mat.set_shader_parameter("tint_strength", float(info["tint_strength"]))
	mat.set_shader_parameter("snow_tint_neutral", float(info.get("snow_tint_neutral", 0.0)))
	if FileAccess.file_exists(dir.path_join("relief.png.import")) and not OS.get_cmdline_user_args().has("--no-relief"):
		mat.set_shader_parameter("relief", load(dir.path_join("relief.png")))
		mat.set_shader_parameter("has_relief", true)
		mat.set_shader_parameter("relief_strength", float(info.get("relief_strength", 1.0)))
		if FileAccess.file_exists(dir.path_join("ripple.png.import")):
			mat.set_shader_parameter("ripple", load(dir.path_join("ripple.png")))
			mat.set_shader_parameter("has_ripple", true)
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--relief-strength="):
				mat.set_shader_parameter("relief_strength", float(a.split("=")[1]))
			if a.begins_with("--ao-strength="):
				mat.set_shader_parameter("ao_strength", float(a.split("=")[1]))
	if info.has("palette2") and FileAccess.file_exists(dir.path_join("mask2.png.import")):  # a mixed map
		var pal2 := String(info["palette2"])
		var p2: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(pdir.path_join(pal2 + ".json")))
		var t2 := PackedFloat32Array()
		var m2 := PackedVector3Array()
		for l in p2["layers"]:
			t2.append(float(l["tile_m"]))
			var c2: Array = l["mean_albedo"]
			var lin2 := Color(float(c2[0]) / 255.0, float(c2[1]) / 255.0, float(c2[2]) / 255.0).srgb_to_linear()
			m2.append(Vector3(lin2.r, lin2.g, lin2.b))
		mat.set_shader_parameter("layers2_ah", load(pdir.path_join(pal2 + "_ah.webp")))
		mat.set_shader_parameter("layers2_nr", load(pdir.path_join(pal2 + "_nr.webp")))
		mat.set_shader_parameter("tile2_m", t2)
		mat.set_shader_parameter("mean2_albedo", m2)
		mat.set_shader_parameter("mask2", load(dir.path_join("mask2.png")))
		mat.set_shader_parameter("has_p2", true)
		print("terrain v3: second palette %s by mask2" % pal2)
	var vdir := "res://assets/terrain/v3"
	if FileAccess.file_exists(vdir.path_join("paved.json")) and not OS.get_cmdline_user_args().has("--old-paving"):
		var pv: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(vdir.path_join("paved.json")))
		var pt := PackedFloat32Array()
		for l in pv["layers"]:
			pt.append(float(l["tile_m"]))
		mat.set_shader_parameter("paved_ah", load(vdir.path_join("paved_ah.webp")))
		mat.set_shader_parameter("paved_nr", load(vdir.path_join("paved_nr.webp")))
		mat.set_shader_parameter("paved_tile_m", pt)
		mat.set_shader_parameter("paved_v3", true)
		var ap := dir.path_join("apron_sdf.png")
		if ResourceLoader.exists(ap):
			mat.set_shader_parameter("apron_sdf", load(ap))
			mat.set_shader_parameter("apron_on", true)
	mat.set_shader_parameter("mean_albedo", means)
	mat.set_shader_parameter("rough_scale", rough)
	mat.set_shader_parameter("albedo_scale", albs)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--terrain-debug="):
			mat.set_shader_parameter("debug_view", int(a.split("=")[1]))
	print("terrain v3: %s, palette %s" % [map_name, pal])
	return mat
