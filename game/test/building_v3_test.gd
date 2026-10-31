extends GdUnitTestSuite
## v3 buildings (LANCE-21): a model under assets/v3/objects takes the shared library materials, ObjectsView prefers it
## behind ArtV3, swaps to the damaged state at half damage and to the destroyed state on destroy, and falls back to the
## current art for a building with no v3 model.


func after_test() -> void:
	ArtV3.enabled = ArtV3._detect()


func test_every_surface_gets_a_library_material() -> void:
	var path := BuildingV3.model_path("largefueltank")
	assert_str(path).is_not_empty()
	var node: Node3D = (load(path) as PackedScene).instantiate()
	BuildingV3.dress(node)
	var seen := 0
	for mi in node.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			assert_object(mesh.surface_get_material(i)).is_instanceof(ShaderMaterial)
			seen += 1
	assert_int(seen).is_greater(6)
	node.free()


func test_states_exist_and_switch_off_with_art_v3() -> void:
	for st in ["", "_damaged", "_destroyed"]:
		assert_str(BuildingV3.model_path("largefueltank", st)).is_not_empty()
	assert_str(BuildingV3.model_path("pine1")).is_empty()  # no v3 model: the current art stays
	ArtV3.enabled = false
	assert_str(BuildingV3.model_path("largefueltank")).is_empty()


func test_damage_swaps_then_destroy_swaps() -> void:
	ArtV3.enabled = true
	var view := ObjectsView.new()
	add_child(view)
	var intact: Node3D = view._instance_state(BuildingV3.model_path("largefueltank"))
	view.add_child(intact)
	view.nodes[7] = intact
	view._appearance[7] = "largefueltank"
	view.set_damage(7, 0.3)
	assert_object(view.nodes[7]).is_same(intact)
	view.set_damage(7, 0.6)
	assert_object(view.nodes[7]).is_not_same(intact)
	var hurt: Node3D = view.nodes[7]
	view.destroy(7)
	assert_object(view.nodes[7]).is_not_same(hurt)
	view.queue_free()


const STORAGE_FAMILY := ["largefueltank", "smallfueltank", "pipetank", "liquidstorage", "watertower", "grainstorage",
	"civstoragea", "civstorageb", "civstoragec"]


func test_storage_family_has_three_states_with_two_lods() -> void:
	for app in STORAGE_FAMILY:
		for st in ["", "_damaged", "_destroyed"]:
			var path := BuildingV3.model_path(app, st)
			assert_str(path).is_not_empty()
			var node: Node3D = (load(path) as PackedScene).instantiate()
			assert_object(node.find_child("lod0", true, false)).is_not_null()
			assert_object(node.find_child("lod1", true, false)).is_not_null()
			BuildingV3.dress(node)
			assert_float((node.find_child("lod0", true, false) as GeometryInstance3D).visibility_range_end).is_equal(BuildingV3.LOD_M)
			assert_float((node.find_child("lod1", true, false) as GeometryInstance3D).visibility_range_begin).is_equal(BuildingV3.LOD_M)
			node.free()
