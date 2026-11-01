extends SceneTree
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		var n: Node3D = (load(BuildingV3.model_path(app)) as PackedScene).instantiate()
		var l := n.find_child("lod0", true, false) as MeshInstance3D
		var s := ""
		for i in l.mesh.get_surface_count():
			s += "%s(%d) " % [l.mesh.surface_get_material(i).resource_name, (l.mesh.surface_get_arrays(i)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3]
		print("ML ", app, " ", s)
	quit()
