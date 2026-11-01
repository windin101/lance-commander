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
