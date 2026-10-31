extends SceneTree
## Wall/gate/post v3 models vs the original's bounds, per LOD and state, plus material resolution.
func _aabb(n: Node, skip_doors := false) -> AABB:
	var out := AABB()
	var first := true
	var list: Array = n.find_children("*", "MeshInstance3D", true, false)
	if n is MeshInstance3D:
		list.append(n)
	for m in list:
		var mi := m as MeshInstance3D
		if mi.mesh == null:
			continue
		var bb: AABB = (n.global_transform.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb() if mi != n else mi.mesh.get_aabb()
		if first:
			out = bb
			first = false
		else:
			out = out.merge(bb)
	return out
func _init() -> void:
	var apps := []
	for st in ["s_", "l_", "d_"]:
		for k in ["lightwall", "mediumwall", "heavywall", "lightpost", "mediumpost", "heavypost", "lightgate", "mediumgate", "heavygate"]:
			apps.append(st + k)
	for app in apps:
		var orig := "res://assets/objects/%s.glb" % app
		if not ResourceLoader.exists(orig):
			continue
		var o: Node3D = (load(orig) as PackedScene).instantiate()
		root.add_child(o)
		var ob := _aabb(o)
		var line := "%-14s orig x[%5.1f,%5.1f] y[%4.1f,%4.1f] z[%5.1f,%5.1f]" % [app, ob.position.x, ob.end.x, ob.position.y, ob.end.y, ob.position.z, ob.end.z]
		o.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			if p == "":
				line += "  | %s MISSING" % st
				continue
			var n: Node3D = (load(p) as PackedScene).instantiate()
			root.add_child(n)
			for lod in ["lod0", "lod1"]:
				var l := n.find_child(lod, true, false)
				if l == null:
					line += "  | %s%s none" % [st, lod]
					continue
				var b := _aabb(l)
				line += "  | %s%s z[%5.1f,%5.1f] x[%4.1f,%4.1f]" % [st.substr(1, 3), lod, b.position.z, b.end.z, b.position.x, b.end.x]
			n.queue_free()
		print(line)
	quit()
