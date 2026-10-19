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
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain.gdshader")
	mat.set_shader_parameter("colour_map", load(texture_dir.path_join("burnin.jpg")))
	var detail_path := texture_dir.path_join("detail.tga")
	if ResourceLoader.exists(detail_path):
		mat.set_shader_parameter("detail_map", load(detail_path))
	mat.set_shader_parameter("rock_noise", _noise_texture(false, 256, 0.02))
	_overlay_layer(mat)
	ground.material_override = mat
	# The colour map already carries the hills' own shading and cast shadows (burn-in): the ground must
	# not shadow itself again. It still receives the shadows of everything standing on it.
	ground.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(ground)
	if map.water_level_m > -100.0:
		add_child(_water(texture_dir))


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
	var info_path := "res://assets/terrain/overlays.json"
	if not FileAccess.file_exists(info_path) or not ResourceLoader.exists("res://assets/terrain/overlays.png"):
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
	mat.set_shader_parameter("overlay_atlas", load("res://assets/terrain/overlays.png"))
	mat.set_shader_parameter("overlay_index", ImageTexture.create_from_image(idx))
	mat.set_shader_parameter("cement_weight", ImageTexture.create_from_image(weight))
	mat.set_shader_parameter("atlas_cols", float(info["cols"]))
	mat.set_shader_parameter("atlas_tile", float(info["tile"]))
	mat.set_shader_parameter("atlas_pad", float(info["pad"]))
	mat.set_shader_parameter("vertices_per_side", float(n))
