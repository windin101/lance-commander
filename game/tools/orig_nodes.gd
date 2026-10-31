extends SceneTree
func _walk(n: Node, depth: int, base: Transform3D) -> void:
	var s := "  ".repeat(depth) + n.name + " " + n.get_class()
	if n is MeshInstance3D and (n as MeshInstance3D).mesh:
		var mi := n as MeshInstance3D
		var b: AABB = (base.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb()
		s += " x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f]" % [b.position.x, b.end.x, b.position.y, b.end.y, b.position.z, b.end.z]
	print("ON ", s)
	for ch in n.get_children():
		_walk(ch, depth + 1, base)
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		var n: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		root.add_child(n)
		print("ON == ", app)
		_walk(n, 0, n.global_transform)
	quit()
