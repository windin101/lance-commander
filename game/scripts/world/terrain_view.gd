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
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load(texture_dir.path_join("burnin.jpg"))
	mat.roughness = 0.95
	var detail_path := texture_dir.path_join("detail.tga")
	if ResourceLoader.exists(detail_path):
		mat.detail_enabled = true
		mat.detail_albedo = load(detail_path)
		mat.detail_blend_mode = BaseMaterial3D.BLEND_MODE_MUL
		mat.detail_uv_layer = BaseMaterial3D.DETAIL_UV_2
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	ground.material_override = mat
	add_child(ground)
	if map.water_level_m > -100.0:
		add_child(_water(texture_dir))


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
			st.set_uv(Vector2(float(col) / n, float(row) / n) * tiling)
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
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load(texture_dir.path_join("water.tga"))
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.metallic_specular = 0.8
	mat.roughness = 0.15
	water.material_override = mat
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return water
