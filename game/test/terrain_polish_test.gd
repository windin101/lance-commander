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


# --- round 3 (2026-11-01): dead trees, shore refinement, understorey plants --------------------------------------------

func test_every_dead_tree_is_a_grown_tree_with_three_variants() -> void:
	var info := JSON.parse_string(FileAccess.get_file_as_string("res://assets/trees/trees.json")) as Dictionary
	var dead := 0
	for app in info["types"]:
		if not String(app).ends_with("dead"):
			continue
		dead += 1
		var t: Dictionary = info["types"][app]
		assert_str(String(t["kind"])).is_equal("dead")
		assert_int(int(t["variants"])).is_equal(ObjectsView.DEAD_VARIANTS)
		assert_int(int(t["tris"])).is_between(400, 2500)   # branching, but light enough for a MultiMesh of hundreds
		var scene := (load("res://assets/trees/%s.glb" % app) as PackedScene).instantiate()
		for v in ObjectsView.DEAD_VARIANTS:
			var sfx := "" if v == 0 else "_%d" % v
			assert_object(scene.find_child("bark" + sfx, true, false)).is_not_null()
			assert_object(scene.find_child("leaves" + sfx, true, false)).is_not_null()
		scene.free()
	assert_int(dead).is_equal(13)   # 3 pines, 3 oaks, 3 maples, 3 willows, 1 birch


func test_dead_materials_use_their_own_textures() -> void:
	var m := ObjectsView.dead_materials()
	assert_int(m.size()).is_equal(2)
	assert_bool((m[0] as StandardMaterial3D).albedo_texture.resource_path.ends_with("bark_dead.png")).is_true()
	assert_bool(((m[1] as ShaderMaterial).get_shader_parameter("leaf_atlas") as Texture2D).resource_path.ends_with("twigs.png")).is_true()


func test_shore_surface_passes_through_the_vertices_and_stays_near_the_sim_surface() -> void:
	var water := 10.0
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for trial in 40:
		var hv := PackedFloat32Array()
		for i in 16:
			hv.append(water + rng.randf_range(-2.5, 2.5))
		var corners := {Vector2(0, 0): 5, Vector2(1, 0): 6, Vector2(0, 1): 9, Vector2(1, 1): 10}
		for c in corners:
			var r := TerrainView.shore_height(hv, c.x, c.y, water)
			assert_float(r[0]).is_equal_approx(hv[corners[c]], 0.0005)   # exact at the grid vertices: units there are not moved
		for k in 12:
			var tx := rng.randf()
			var ty := rng.randf()
			var r := TerrainView.shore_height(hv, tx, ty, water)
			var bil: float = (1.0 - ty) * ((1.0 - tx) * hv[5] + tx * hv[6]) + ty * ((1.0 - tx) * hv[9] + tx * hv[10])
			assert_float(absf(r[0] - bil)).is_less(TerrainView.SHORE_MAX_DEV + 0.001)   # never more than the stated tolerance
			assert_float(r[3]).is_between(0.0, 1.0)


func test_shore_blend_closes_the_seam_to_the_untouched_mesh() -> void:
	# a quad whose ground is more than the band above the water takes no refinement: it equals the bilinear surface
	var hv := PackedFloat32Array()
	for i in 16:
		hv.append(30.0 + float(i % 4) * 1.5 + float(i / 4) * 0.7 + (3.0 if i == 6 else 0.0))
	for tx in [0.0, 0.3, 0.77, 1.0]:
		var r := TerrainView.shore_height(hv, tx, 0.4, 10.0)
		var bil: float = 0.6 * ((1.0 - tx) * hv[5] + tx * hv[6]) + 0.4 * ((1.0 - tx) * hv[9] + tx * hv[10])
		assert_float(r[0]).is_equal_approx(bil, 0.0001)
		assert_float(r[3]).is_equal(0.0)


func test_catmull_rom_weights_sum_to_one_and_reproduce_a_line() -> void:
	for t in [0.0, 0.2, 0.5, 0.9, 1.0]:
		var w := TerrainView._cr_w(t)
		assert_float(w[0] + w[1] + w[2] + w[3]).is_equal_approx(1.0, 0.0001)
		assert_float(0.0 * w[0] + 1.0 * w[1] + 2.0 * w[2] + 3.0 * w[3]).is_equal_approx(1.0 + t, 0.0001)   # linear data stay linear


func test_plant_meshes_are_light_and_name_their_atlas_cell() -> void:
	var card := TerrainPlantsV3.cards_mesh(1, 3, 1.0, 1.0)
	assert_int(card.surface_get_array_len(0)).is_equal(18)
	var uv2: PackedVector2Array = card.surface_get_arrays(0)[Mesh.ARRAY_TEX_UV2]
	assert_float(uv2[0].x).is_equal(1.0)
	var dome := TerrainPlantsV3.dome_mesh(11)
	assert_int(dome.surface_get_array_len(0)).is_less(400)
	var img := (load("res://assets/terrain/v3/plants_atlas.png") as Texture2D).get_image()
	assert_int(img.get_width()).is_equal(1024)
	assert_int(img.get_height()).is_equal(1024)
	for cell in 4:
		var opaque := 0
		var total := 0
		for y in range(0, 512, 8):
			for x in range(0, 512, 8):
				total += 1
				if img.get_pixel((cell % 2) * 512 + x, (cell / 2) * 512 + y).a > 0.5:
					opaque += 1
		assert_int(opaque).is_greater(total / 40)   # something is drawn in every cell


func test_biomes_scale_plants_by_palette() -> void:
	for k in TerrainPlantsV3.biome_for("lunar"):
		if k != "dark":
			assert_float(float(TerrainPlantsV3.biome_for("lunar")[k])).is_equal(0.0)   # nothing on the moon
	assert_float(float(TerrainPlantsV3.biome_for("arid")["fern"])).is_equal(0.0)
	assert_float(float(TerrainPlantsV3.biome_for("arid")["scrub"])).is_greater(0.5)
	assert_float(float(TerrainPlantsV3.biome_for("temperate_muted")["hedge"])).is_greater(0.5)
	assert_float(float(TerrainPlantsV3.biome_for("no_such_palette")["bush"])).is_equal(1.0)   # unknown palettes get the temperate set
	assert_float(float(TerrainPlantsV3.biome_for("snow")["flower"])).is_equal(0.0)


func test_plants_on_a_real_map_stay_in_bounds_and_off_paving() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var pal := JSON.parse_string(FileAccess.get_file_as_string("res://assets/terrain/v3/palettes/temperate_muted.json")) as Dictionary
	var d := TerrainDressV3.new()
	add_child(d)
	d.build(sm.world.map, "mc2_01", pal["layers"])
	var pc: Dictionary = d.veg_counts.get("plants", {})
	assert_int(int(pc.get("bush", -1))).is_between(100, TerrainPlantsV3.MAX_BUSH)
	assert_int(int(pc.get("fern", -1))).is_between(1, TerrainPlantsV3.MAX_FERN)
	assert_int(int(pc.get("flower", -1))).is_between(1, TerrainPlantsV3.MAX_FLOWER)
	assert_int(int(pc.get("hedge", -1))).is_between(1, TerrainPlantsV3.MAX_HEDGE)
	assert_int(int(pc.get("total", 0))).is_less(60000)
	# nothing grows on the apron: every point the paving mask covers is refused
	var apron: Image = d._apron
	assert_object(apron).is_not_null()
	var paved := 0
	var wrongly_ok := 0
	var pl: TerrainPlantsV3 = d.plants_v3
	for y in range(0, apron.get_height(), 97):
		for x in range(0, apron.get_width(), 97):
			if apron.get_pixel(x, y).r > 0.6:   # well inside the cement
				paved += 1
				var p := Vector2(-sm.world.map.half_m + (x + 0.5) / apron.get_width() * sm.world.map.half_m * 2.0, sm.world.map.half_m - (y + 0.5) / apron.get_height() * sm.world.map.half_m * 2.0)
				if pl._ok(p, [0, 1, 2, 3, 4, 5, 6, 7], -100.0, 100.0, 0.0):
					wrongly_ok += 1
	assert_int(paved).is_greater(20)
	assert_int(wrongly_ok).is_equal(0)
	d.queue_free()


func test_no_plants_on_a_lunar_map() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_13")
	var pal := JSON.parse_string(FileAccess.get_file_as_string("res://assets/terrain/v3/palettes/lunar.json")) as Dictionary
	var d := TerrainDressV3.new()
	add_child(d)
	d.build(sm.world.map, "mc2_13", pal["layers"])
	var pc: Dictionary = d.veg_counts.get("plants", {})
	assert_int(int(pc.get("bush", -1))).is_equal(0)
	assert_int(int(pc.get("fern", -1))).is_equal(0)
	assert_int(int(pc.get("flower", -1))).is_equal(0)
	assert_int(int(pc.get("hedge", -1))).is_equal(0)
	assert_int(int(pc.get("total", -1))).is_equal(0)
	d.queue_free()
