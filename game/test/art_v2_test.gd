extends GdUnitTestSuite
## HD rework (v2) dev switch: off by default; on, the loaders take res://assets/v2/ models with the v2 shaders.


func before_test() -> void:
	ArtV3.enabled = false  # v3 is the default and outranks v2


func after_test() -> void:
	ArtV2.enabled = false
	ArtV3.enabled = ArtV3._detect()


func test_switch_is_off_by_default() -> void:
	assert_bool(ArtV2.enabled).is_false()
	assert_str(ArtV2.model_path("mechs", "bushwacker")).is_equal("")


func test_mech_view_takes_the_v2_model_and_shader() -> void:
	if not ResourceLoader.exists("res://assets/v2/mechs/bushwacker.glb"):
		return  # staged by tools/art/hd_v2.py
	ArtV2.enabled = true
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var bw: SimUnit = sm.world.units[1]
	var v := MechView.new()
	add_child(v)
	v.setup(bw, sm.world.map)
	assert_str(v._paint_name).is_equal("bushwacker_v2")
	var mi: MeshInstance3D = v.model.find_children("*", "MeshInstance3D", true, false)[0]
	assert_object(mi.material_override).is_instanceof(ShaderMaterial)
	var player: AnimationPlayer = v.model.find_child("AnimationPlayer", true, false)
	for a in ["Idle", "Walk", "FallForward"]:
		assert_bool(player.has_animation(a)).is_true()
	bw.status = SimUnit.Status.DESTROYED
	v.sync(1.0)
	var burnt := mi.material_override as ShaderMaterial
	assert_float(float(burnt.get_shader_parameter("scorch"))).is_equal(1.0)
	v.queue_free()


func test_environment_reaches_v2_materials() -> void:
	if not ResourceLoader.exists("res://assets/v2/mechs/bushwacker.glb"):
		return
	var root: Node3D = load("res://assets/v2/mechs/bushwacker.glb").instantiate()
	MechPaint.apply(root, "bushwacker_v2", Color.RED, Color.GREEN, Color.BLUE, "mechs")
	MechPaint.set_environment(0.4, 0.7, Color(0.5, 0.5, 0.5))
	var mi: MeshInstance3D = root.find_children("*", "MeshInstance3D", true, false)[0]
	var m := mi.material_override as ShaderMaterial
	assert_float(float(m.get_shader_parameter("snow"))).is_equal_approx(0.7, 0.001)
	MechPaint.set_environment(0.25, 0.0, Color(0.56, 0.5, 0.4))
	root.free()


func test_v2_building_is_dressed() -> void:
	if not ResourceLoader.exists("res://assets/v2/objects/quonsetclean.glb"):
		return
	var root: Node3D = load("res://assets/v2/objects/quonsetclean.glb").instantiate()
	ArtV2.dress_object(root, "quonsetclean")
	var mi: MeshInstance3D = root.find_children("*", "MeshInstance3D", true, false)[0]
	for i in mi.mesh.get_surface_count():
		assert_object(mi.mesh.surface_get_material(i)).is_instanceof(ShaderMaterial)
	root.free()


func test_weather_table_covers_every_mission() -> void:
	var w: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/unit_weather.json"))
	for i in range(1, 25):
		assert_bool(w.has("mc2_%02d" % i)).is_true()
