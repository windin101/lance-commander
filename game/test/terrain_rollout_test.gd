extends GdUnitTestSuite
## Terrain polish rollout, batch 1 (2026-11-02): the night/airless fill shared by the dressing materials, and the per-map
## layer_albedo_scale data (palettes.json maps.<m>.layer_albedo_scale -> terrain_v3.json, by palette slot name).

const SLOTS := ["ground", "ground2", "rock", "cliff", "scree", "dust", "forest", "wet"]


func test_dressing_shaders_have_a_fill_floor_like_the_ground() -> void:
	for p in ["res://shaders/grass.gdshader", "res://shaders/plants.gdshader", "res://shaders/leaves.gdshader", "res://shaders/scatter_v3.gdshader"]:
		var sh := load(p) as Shader
		assert_object(sh).is_not_null()
		var names := sh.get_shader_uniform_list().map(func(u): return String(u["name"]))
		assert_bool(names.has("fill")).is_true()
	# the ground's own floor is what they follow
	var gnames := (load("res://shaders/terrain_v3.gdshader") as Shader).get_shader_uniform_list().map(func(u): return String(u["name"]))
	assert_bool(gnames.has("shadow_fill")).is_true()


func test_ground_fill_follows_the_ground_material_and_defaults_to_the_ground_default() -> void:
	var d := TerrainDressV3.new()
	assert_float(d.ground_fill()).is_equal(0.05)   # no ground material: the shader's default
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/terrain_v3.gdshader")
	d.ground_material = m
	assert_float(d.ground_fill()).is_equal(0.05)   # parameter not set
	m.set_shader_parameter("shadow_fill", 0.3)
	assert_float(d.ground_fill()).is_equal_approx(0.3, 0.0001)
	var sm := d._scatter_mat()
	assert_float(float(sm.get_shader_parameter("fill"))).is_equal_approx(0.3, 0.0001)
	d.free()


func test_layer_albedo_scale_is_per_slot_and_the_json_matches_palettes() -> void:
	var pal: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://../tools/art/terrain/palettes.json"))
	var seen := 0
	for m in pal["maps"]:
		var src: Dictionary = pal["maps"][m]
		var jp := "res://assets/terrain/v3/%s/terrain_v3.json" % m
		if not FileAccess.file_exists(jp):
			continue
		var info: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(jp))
		assert_bool(info.has("layer_albedo_scale")).is_equal(src.has("layer_albedo_scale"))
		if src.has("layer_albedo_scale"):
			seen += 1
			assert_dict(info["layer_albedo_scale"]).is_equal(src["layer_albedo_scale"])
			for slot in src["layer_albedo_scale"]:
				assert_bool(SLOTS.has(slot)).is_true()   # a slot name, not an index
				var k := float(src["layer_albedo_scale"][slot])
				assert_float(k).is_between(0.4, 1.2)   # a gentle per-map nudge, never a blackout or a glare
	assert_int(seen).is_greater(1)   # mc2_04 and mc2_07 carry it


## Batch 2 (2026-11-02): the shore band follows real water, and the per-map water and cover keys.
func test_shore_near_texture_is_one_at_the_water_and_zero_far_from_it() -> void:
	var m := SimMap.new()
	m.vertices_per_side = 40
	m.vertex_m = 25.6
	m.water_level_m = 5.0
	m.elevation_m = PackedFloat32Array()
	for r in 40:
		for c in 40:
			m.elevation_m.append(0.0 if c < 4 else 20.0)   # water along the west edge only
	var img := TerrainView.shore_near_texture(m).get_image()
	assert_int(img.get_width()).is_equal(40)
	assert_float(img.get_pixel(1, 20).r).is_equal_approx(1.0, 0.01)    # in the water
	assert_float(img.get_pixel(4, 20).r).is_greater(0.9)               # at the waterline
	assert_float(img.get_pixel(5, 20).r).is_greater(0.5)               # one vertex out
	assert_float(img.get_pixel(12, 20).r).is_less(0.01)                # 200 m out: no beach
	assert_float(img.get_pixel(39, 5).r).is_less(0.01)


func test_the_water_shader_has_the_per_map_knobs_and_the_json_keys_are_sane() -> void:
	var names := (load("res://shaders/water_v3.gdshader") as Shader).get_shader_uniform_list().map(func(u): return String(u["name"]))
	for n in ["absorb_k", "spec_k", "glow"]:
		assert_bool(names.has(n)).is_true()
	var tn := (load("res://shaders/terrain_v3.gdshader") as Shader).get_shader_uniform_list().map(func(u): return String(u["name"]))
	assert_bool(tn.has("shore_near")).is_true()
	var pal: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://../tools/art/terrain/palettes.json"))
	var lim := {"water_absorb_k": [0.5, 12.0], "water_reflect": [0.0, 1.5], "water_glow": [0.0, 2.0], "cover_gain": [0.1, 1.0]}
	var seen := 0
	for m in pal["maps"]:
		var jp := "res://assets/terrain/v3/%s/terrain_v3.json" % m
		if not FileAccess.file_exists(jp):
			continue
		var info: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(jp))
		for k in lim:
			assert_bool(info.has(k)).is_equal(pal["maps"][m].has(k))
			if info.has(k):
				seen += 1
				assert_float(float(info[k])).is_equal(float(pal["maps"][m][k]))
				assert_float(float(info[k])).is_between(lim[k][0], lim[k][1])
	assert_int(seen).is_greater(3)
	# lunar: no vegetation, warm_k stays 0 (the shore texture is only built where there is water)
	assert_bool(pal["maps"]["mc2_13"]["palette"] == "lunar").is_true()
