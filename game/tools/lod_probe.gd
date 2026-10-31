extends SceneTree
func _init() -> void:
	var ps: PackedScene = load(BuildingV3.model_path("d_lightwall"))
	var a: Node3D = ps.instantiate()
	BuildingV3.dress(a)
	var b: Node3D = ps.instantiate()
	for n in [a, b]:
		for l in ["lod0", "lod1"]:
			var m := n.find_child(l, true, false) as GeometryInstance3D
			print(l, " begin ", m.visibility_range_begin, " end ", m.visibility_range_end, " surfaces ", (m as MeshInstance3D).mesh.get_surface_count(), " mat0 ", (m as MeshInstance3D).mesh.surface_get_material(0))
	quit()
