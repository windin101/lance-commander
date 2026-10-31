extends SceneTree
## godot --headless --path game -s res://tools/orig_bounds.gd -- app1 app2 ...   (original model bounds, triangles)
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		var p := "res://assets/objects/%s.glb" % app
		if not ResourceLoader.exists(p):
			print("OB ", app, " MISSING"); continue
		var n: Node3D = (load(p) as PackedScene).instantiate()
		root.add_child(n)
		var bb := AABB(); var first := true; var tris := 0; var surf := 0
		for m in n.find_children("*", "MeshInstance3D", true, false):
			var mi := m as MeshInstance3D
			if mi.name.to_lower().begins_with("litwin"): continue
			var b: AABB = (n.global_transform.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb()
			bb = b if first else bb.merge(b); first = false
			surf += mi.mesh.get_surface_count()
			for s in mi.mesh.get_surface_count():
				tris += (mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
		print("OB %-18s x[%6.1f,%6.1f] y[%5.1f,%5.1f] z[%6.1f,%6.1f] size %.0fx%.0fx%.0f tris %d surf %d" % [app, bb.position.x, bb.end.x, bb.position.y, bb.end.y, bb.position.z, bb.end.z, bb.size.x, bb.size.y, bb.size.z, tris, surf])
	quit()
