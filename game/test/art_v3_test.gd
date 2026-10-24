extends GdUnitTestSuite
## HD rework v3 dev switch (tools/art/v3): off by default; on, MechView takes res://assets/v3/ models with the v3
## shader and a scheme.


func after_test() -> void:
	ArtV3.enabled = false


func test_switch_is_off_by_default() -> void:
	assert_bool(ArtV3.enabled).is_false()
	assert_str(ArtV3.model_path("mechs", "atlas")).is_equal("")


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
	u.status = SimUnit.Status.DESTROYED
	v.sync(1.0)
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
	ArtV3.set_scheme(mat, PaintScheme.named("davion"))
	assert_int(int(mat.get_shader_parameter("pattern"))).is_equal(PaintScheme.PATTERNS.find("thorin"))
