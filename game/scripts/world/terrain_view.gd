class_name TerrainView
extends Node3D
## Visible terrain and water for a SimMap. Godot axes: X east, Y up, -Z north,
## so a sim position (x, y) is Vector3(x, height, -y).
## The colour map covers the whole map side (vertices x 128 world units), as
## the original's TerrainColorMap does.

var map: SimMap


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
	ground.material_override = mat
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


## Water plane at the mission's water level; opacity follows depth, from the
## mission FIT's AlphaShallow / AlphaMiddle / AlphaDeep (125 / 175 / 255).
func _water(texture_dir: String) -> MeshInstance3D:
	var n := map.vertices_per_side
	var shallow_m := float(map.meta.get("water_shallow_depth", 20.0)) * map.meters_per_wu
	var tiling := float(map.meta.get("water_tiling", 48.0))
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for row in n:
		for col in n:
			var pos := Vector2(-map.half_m + col * map.vertex_m, map.half_m - row * map.vertex_m)
			var depth := map.water_level_m - map.vertex_height(row, col)
			var alpha := 0.0
			if depth > 0.0:
				alpha = lerpf(125.0, 175.0, clampf(depth / shallow_m, 0.0, 1.0)) / 255.0
				if depth > shallow_m:
					alpha = lerpf(175.0, 255.0, clampf((depth - shallow_m) / (shallow_m * 2.0), 0.0, 1.0)) / 255.0
			st.set_color(Color(1, 1, 1, alpha))
			st.set_uv(Vector2(float(col) / n, float(row) / n) * tiling * 0.25)
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
	# Mission [Water] Frequency / Ampliture (world units) -> a gentle swell in metres.
	var amp := float(map.meta.get("water_amplitude", 3.0)) * map.meters_per_wu
	mat.set_shader_parameter("swell_height", clampf(amp, 0.1, 1.5))
	water.material_override = mat
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return water
