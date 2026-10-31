extends GdUnitTestSuite
## HD rework v3 switch (tools/art/v3): on by default since 2026-10-25; on, MechView takes res://assets/v3/ models with the v3
## shader and a scheme.


func after_test() -> void:
	ArtV3.enabled = ArtV3._detect()


func test_switch_is_on_by_default() -> void:
	assert_bool(ArtV3._detect()).is_true()  # the test runner passes no --no-art-v3
	var was := ArtV3.enabled
	ArtV3.enabled = false
	assert_str(ArtV3.model_path("mechs", "atlas")).is_equal("")
	ArtV3.enabled = was


func test_mech_view_takes_the_v3_model_and_shader() -> void:
	if not ResourceLoader.exists("res://assets/v3/mechs/atlas.glb"):
		return  # staged by tools/art/v3/v3_mech.py
	ArtV3.enabled = true
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit = sm.world.units[1]
	u.model = "atlas"
	var v := MechView.new()
	add_child(v)
	v.setup(u, sm.world.map)
	assert_str(v._paint_name).is_equal("atlas_v3")
	var mis: Array = v.model.find_children("*", "MeshInstance3D", true, false)
	assert_int(mis.size()).is_greater(10)  # one rigid mesh per part
	var mat := (mis[0] as MeshInstance3D).material_override as ShaderMaterial
	assert_object(mat).is_not_null()
	assert_str(mat.shader.resource_path).is_equal("res://shaders/unit_v3.gdshader")
	var player: AnimationPlayer = v.model.find_child("AnimationPlayer", true, false)
	for a in ["Idle", "Walk", "FallForward"]:
		assert_bool(player.has_animation(a)).is_true()
	var before := v.model
	u.status = SimUnit.Status.DESTROYED
	v.sync(1.0)
	if MechView.v3_wreck_path("atlas_v3", "mechs", "atlas") != "":
		assert_bool(v.model != before).is_true()  # the destroyed variant (tools/art/v3/wreck_mesh.py) replaces the model
		assert_object(v.player).is_null()
	else:
		var burnt := (mis[0] as MeshInstance3D).material_override as ShaderMaterial
		assert_float(float(burnt.get_shader_parameter("scorch"))).is_equal(1.0)
	v.queue_free()


func test_scheme_regions_reach_the_shader() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/unit_v3.gdshader")
	ArtV3.set_scheme(mat, PaintScheme.named("steiner"))
	var steel: PackedFloat32Array = mat.get_shader_parameter("region_steel")
	assert_float(steel[PaintScheme.REGIONS.find("weapons")]).is_equal(1.0)
	assert_float(float(mat.get_shader_parameter("band_on"))).is_equal(1.0)
	ArtV3.set_scheme(mat, PaintScheme.named("bandits"))
	assert_int(int(mat.get_shader_parameter("pattern"))).is_equal(PaintScheme.PATTERNS.find("arkab"))


func test_wreck_variant_path() -> void:
	# a v3 unit with a <name>_wreck.glb gets it; a non-v3 paint name or a unit without one keeps the scorched freeze
	assert_str(MechView.v3_wreck_path("atlas_hd", "mechs", "atlas")).is_equal("")
	assert_str(MechView.v3_wreck_path("zzzz_v3", "mechs", "zzzz")).is_equal("")
	if ResourceLoader.exists("res://assets/v3/mechs/atlas_wreck.glb"):
		assert_str(MechView.v3_wreck_path("atlas_v3", "mechs", "atlas")).is_equal("res://assets/v3/mechs/atlas_wreck.glb")
		var root: Node = load("res://assets/v3/mechs/atlas_wreck.glb").instantiate()
		var mis: Array = root.find_children("*", "MeshInstance3D", true, false)
		assert_int(mis.size()).is_greater(14)  # the parts plus plates, frame and debris
		var arrays: Array = (mis[0] as MeshInstance3D).mesh.surface_get_arrays(0)
		assert_bool(arrays[Mesh.ARRAY_COLOR] != null).is_true()  # the burn
		root.free()


func test_every_wreck_variant_loads_with_burn_and_a_parent() -> void:
	# tools/art/v3/wreck_mesh.py: <name>_wreck.glb beside its model, same atlases, burn in COLOR_0, wheels/tracks renamed wrecked_*
	for folder in ["mechs", "vehicles"]:
		var dir := "res://assets/v3/%s/" % folder
		for f in DirAccess.get_files_at(dir):
			if not f.ends_with("_wreck.glb"):
				continue
			var parent := f.replace("_wreck.glb", ".glb")
			assert_bool(ResourceLoader.exists(dir + parent)).override_failure_message(f + " has no parent model").is_true()
			var root: Node = (load(dir + f) as PackedScene).instantiate()
			var mis: Array = root.find_children("*", "MeshInstance3D", true, false)
			assert_int(mis.size()).override_failure_message(f).is_greater(5)
			assert_array(root.find_children("wheel_*", "Node3D", true, false)).override_failure_message(f + ": a baked wheel keeps its rig name").is_empty()
			var arrays: Array = (mis[0] as MeshInstance3D).mesh.surface_get_arrays(0)
			assert_bool(arrays[Mesh.ARRAY_COLOR] != null).override_failure_message(f + " carries no burn").is_true()
			root.free()


# --- unit brightness calibration (tools/art/v3/unit_lum.py): the mission look reaches every v3 unit material ---
func test_unit_look_day_night_and_bay_defaults() -> void:
	var root := Node3D.new()
	add_child(root)
	var mi := MeshInstance3D.new()
	mi.mesh = BoxMesh.new()
	root.add_child(mi)
	var mat := ArtV3.apply(root, "unit_look_probe", {})
	ArtV3.set_unit_look("mc2_12", false)  # a measured day map: its own albedo gain, no fill, metal as is
	assert_float(float(mat.get_shader_parameter("unit_lift"))).is_equal_approx(ArtV3.UNIT_GAIN["mc2_12"], 0.0001)
	assert_float(float(mat.get_shader_parameter("unit_fill"))).is_equal(0.0)
	assert_float(float(mat.get_shader_parameter("night_metal"))).is_equal(0.0)
	ArtV3.set_unit_look("mc2_99", false)  # an unmeasured day map (every campaign map is in the table now): the default day lift
	assert_float(float(mat.get_shader_parameter("unit_lift"))).is_equal_approx(ArtV3.UNIT_DAY_LIFT, 0.0001)
	ArtV3.set_unit_look("mc2_23", true)  # a night map: self-lit fill, metal eased, albedo untouched
	assert_float(float(mat.get_shader_parameter("unit_fill"))).is_equal_approx(ArtV3.UNIT_FILL["mc2_23"], 0.0001)
	assert_float(float(mat.get_shader_parameter("unit_lift"))).is_equal(1.0)
	assert_float(float(mat.get_shader_parameter("night_metal"))).is_equal(1.0)
	ArtV3.set_unit_look("mc2_99", true)  # an unmeasured night map: the default fill
	assert_float(float(mat.get_shader_parameter("unit_fill"))).is_equal_approx(ArtV3.UNIT_NIGHT_FILL, 0.0001)
	ArtV3.set_unit_look("", false)
	ArtV3.unit_lift = 1.0  # the Mech Bay and the lab never call set_unit_look: they keep the shader's own defaults
	ArtV3.unit_fill = 0.0
	ArtV3.unit_night = false
	ArtV3._apply_unit_look(mat)
	assert_float(float(mat.get_shader_parameter("unit_lift"))).is_equal(1.0)
	root.queue_free()
