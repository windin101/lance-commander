extends SceneTree
## Per-sub-mesh bounds and a height profile (width x/z by 1 m slice) of an original model. godot --headless --path game -s res://tools/orig_parts.gd -- app
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		var n: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		root.add_child(n)
		print("OP == ", app)
		var slices := {}
		for m in n.find_children("*", "MeshInstance3D", true, false):
			var mi := m as MeshInstance3D
			var xf: Transform3D = n.global_transform.affine_inverse() * mi.global_transform
			var bb: AABB = xf * mi.mesh.get_aabb()
			print("OP part %s x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f] surf %d" % [mi.name, bb.position.x, bb.end.x, bb.position.y, bb.end.y, bb.position.z, bb.end.z, mi.mesh.get_surface_count()])
			if mi.name.to_lower().begins_with("litwin"): continue
			for s in mi.mesh.get_surface_count():
				for v in (mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX] as PackedVector3Array):
					var p := xf * v
					var k := int(floor(p.y))
					var e: Array = slices.get(k, [1e9, -1e9, 1e9, -1e9])
					e[0] = minf(e[0], p.x); e[1] = maxf(e[1], p.x); e[2] = minf(e[2], p.z); e[3] = maxf(e[3], p.z)
					slices[k] = e
		var ks := slices.keys(); ks.sort()
		for k in ks:
			var e: Array = slices[k]
			print("OP  y %2d: x[%.1f,%.1f] w %.1f  z[%.1f,%.1f] d %.1f" % [k, e[0], e[1], e[1] - e[0], e[2], e[3], e[3] - e[2]])
	quit()
