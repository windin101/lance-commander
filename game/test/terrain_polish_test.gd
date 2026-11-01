extends GdUnitTestSuite
## Terrain polish (2026-11-01): water v3 colours and shaders, the ground-cover atlas, the flat MultiMesh buffers of the
## vegetation dress, and bounds on the cover and filler-tree counts (a runaway density would eat memory and load time).


func test_water_colours_run_from_a_lighter_shallow_to_a_darker_deep() -> void:
	for tex in [Color(0.2, 0.3, 0.4), Color(0.1, 0.5, 0.45), Color(0.3, 0.3, 0.3), Color(0.0, 0.0, 0.0)]:
		var cols := TerrainView.water_colours(tex)
		assert_int(cols.size()).is_equal(2)
		var shallow: Color = cols[0]
		var deep: Color = cols[1]
		assert_float(shallow.get_luminance()).is_greater(deep.get_luminance())
		assert_float(deep.get_luminance()).is_greater(0.0)
		assert_float(shallow.get_luminance()).is_less(0.6)   # never a white sea


func test_the_new_shaders_compile_as_spatial() -> void:
	for p in ["res://shaders/water_v3.gdshader", "res://shaders/grass.gdshader", "res://shaders/terrain_v3.gdshader"]:
		var sh := load(p) as Shader
		assert_object(sh).is_not_null()
		assert_int(sh.get_mode()).is_equal(Shader.MODE_SPATIAL)
	var wp := (load("res://shaders/water_v3.gdshader") as Shader).get_shader_uniform_list()
	var names := wp.map(func(u): return String(u["name"]))
	for n in ["shallow_col", "deep_col", "absorb", "foam_width", "wave_n", "foam_tex"]:
		assert_bool(names.has(n)).is_true()
	var tp := (load("res://shaders/terrain_v3.gdshader") as Shader).get_shader_uniform_list().map(func(u): return String(u["name"]))
	assert_bool(tp.has("water_y")).is_true()   # the wet beach band reads the water level from here
	assert_bool(tp.has("splat_bilinear")).is_true()   # the old class filter stays one flag away


func test_grass_atlas_is_four_cut_out_cells() -> void:
	var img := (load("res://assets/terrain/v3/grass_atlas.png") as Texture2D).get_image()
	assert_int(img.get_width()).is_equal(1024)
	assert_int(img.get_height()).is_equal(256)
	for cell in 4:
		var opaque := 0
		var clear := 0
		for y in range(0, 256, 4):
			for x in range(cell * 256, cell * 256 + 256, 4):
				if img.get_pixel(x, y).a > 0.5:
					opaque += 1
				else:
					clear += 1
		assert_int(opaque).is_greater(150)    # blades are there
		assert_int(clear).is_greater(opaque)  # and most of the cell is cut out


func test_flat_buffers_hold_one_transform_and_colour_per_instance() -> void:
	var m := SimMap.new()
	m.half_m = 1280.0
	var d := TerrainDressV3.new()
	d.map = m
	var k := d._kind(d._clump_mesh(0), 100.0)
	k.mat = StandardMaterial3D.new()
	k.chunk_m = 64.0
	d._flat_put(k, Vector2(10, 20), 5.0, 2.0, 1.5, 0.0, Color(0.2, 0.4, 0.6))
	d._flat_put(k, Vector2(12, 21), 5.0, 1.0, 1.0, 0.5, Color(1, 1, 1))
	d._flat_put(k, Vector2(900, 20), 7.0, 1.0, 1.0, 0.0, Color(1, 1, 1))   # another chunk
	# the buffer is what the renderer reads (the headless dummy server cannot read a MultiMesh back): 12 transform floats
	# (rows: basis x/y/z columns then origin) and 4 colour floats per instance
	var chunks: Dictionary = d._flat[k]
	assert_int(chunks.size()).is_equal(2)
	var found := false
	for key in chunks:
		var buf: PackedFloat32Array = chunks[key]
		if buf.size() == 32:
			found = true
			assert_float(buf[3]).is_equal_approx(10.0, 0.001)        # origin x
			assert_float(buf[11]).is_equal_approx(-20.0, 0.001)      # origin z: sim y is -z
			assert_float(buf[5]).is_equal_approx(3.0, 0.001)         # y scale: size 2 stretched 1.5
			assert_float(buf[0]).is_equal_approx(2.0, 0.001)         # yaw 0: x scale = size
			assert_float(buf[14]).is_equal_approx(0.6, 0.001)        # colour blue
	assert_bool(found).is_true()
	add_child(d)
	assert_int(d._flat_commit("t")).is_equal(3)
	assert_int(d.find_children("t_*", "MultiMeshInstance3D", false, false).size()).is_equal(2)
	d.free()


func test_clump_and_shrub_meshes_are_light() -> void:
	var d := TerrainDressV3.new()
	for i in 4:
		var mesh := d._clump_mesh(i)
		assert_int(mesh.surface_get_array_len(0)).is_equal(18)   # three crossed quads, 6 triangles each cell
	var shrub := d._shrub_mesh()
	assert_int(shrub.surface_get_array_len(0)).is_less(120)
	d.free()


func test_vegetation_counts_stay_in_bounds_on_a_real_map() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var pal := JSON.parse_string(FileAccess.get_file_as_string("res://assets/terrain/v3/palettes/temperate_muted.json")) as Dictionary
	var d := TerrainDressV3.new()
	add_child(d)
	d.build(sm.world.map, "mc2_01", pal["layers"])
	var cover := int(d.veg_counts.get("cover", -1))
	var fillers := int(d.veg_counts.get("fillers", -1))
	# 2.56 km square: at most about 0.4 clumps per square metre of grass-class ground, never an unbounded count
	assert_int(cover).is_between(50000, 1500000)
	# fillers thicken existing forest, they never out-number the placed trees by more than 3:1
	var placed := 0
	var data := JSON.parse_string(FileAccess.get_file_as_string("res://data/maps/mc2_01/objects.json")) as Dictionary
	for o in data["objects"]:
		if ResourceLoader.exists("res://assets/trees/%s.glb" % String((data["types"] as Dictionary).get(str(int(o["type"])), {}).get("appearance", ""))):
			placed += 1
	assert_int(fillers).is_between(1, placed * 3)
	d.queue_free()
