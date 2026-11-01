extends SceneTree
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		var n: Node3D = (load("res://assets/v3/mechs/%s_wreck.glb" % app) as PackedScene).instantiate()
		root.add_child(n)
		print("WN == ", app)
		for m in n.find_children("*", "Node3D", true, false):
			var s := "WN  %s %s" % [m.name, m.get_class()]
			if m is MeshInstance3D and m.mesh:
				var bb: AABB = (n.global_transform.affine_inverse() * m.global_transform) * (m as MeshInstance3D).mesh.get_aabb()
				s += " x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f] surf %d" % [bb.position.x, bb.end.x, bb.position.y, bb.end.y, bb.position.z, bb.end.z, (m as MeshInstance3D).mesh.get_surface_count()]
			print(s)
	quit()
