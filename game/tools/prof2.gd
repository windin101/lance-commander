extends SceneTree
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		var n: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		root.add_child(n)
		var pts := []
		for m in n.find_children("*", "MeshInstance3D", true, false):
			var mi := m as MeshInstance3D
			var xf: Transform3D = n.global_transform.affine_inverse() * mi.global_transform
			for s in mi.mesh.get_surface_count():
				for v in (mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX] as PackedVector3Array):
					pts.append(xf * v)
		var zs := {}
		for p in pts:
			var k := int(round(p.z))
			if not zs.has(k): zs[k] = [p.y, p.y, p.x, p.x]
			zs[k][0] = maxf(zs[k][0], p.y); zs[k][1] = minf(zs[k][1], p.y); zs[k][2] = maxf(zs[k][2], p.x); zs[k][3] = minf(zs[k][3], p.x)
		var ks := zs.keys(); ks.sort()
		print(app, " verts ", pts.size())
		for k in ks: print("  z %d  y[%.1f..%.1f] x[%.1f..%.1f]" % [k, zs[k][1], zs[k][0], zs[k][3], zs[k][2]])
	quit()
