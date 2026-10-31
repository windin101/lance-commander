extends SceneTree
func _init() -> void:
	for app in Array(OS.get_cmdline_user_args()):
		for src in ["res://assets/objects/%s.glb" % app, BuildingV3.model_path(app)]:
			var n: Node3D = (load(src) as PackedScene).instantiate()
			root.add_child(n)
			var tops := {}
			for m in n.find_children("*", "MeshInstance3D", true, false):
				var mi := m as MeshInstance3D
				if mi.name == "lod1": continue
				var xf: Transform3D = n.global_transform.affine_inverse() * mi.global_transform
				for s in mi.mesh.get_surface_count():
					for v in (mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX] as PackedVector3Array):
						var p := xf * v
						var k := int(floor(p.z / 2.0)) * 2
						tops[k] = maxf(tops.get(k, -1.0), p.y)
			var ks := tops.keys(); ks.sort()
			var line := ""
			for k in ks: line += "%d:%.1f " % [k, tops[k]]
			print(app, " ", "orig" if src.contains("objects/") and not src.contains("v3") else "v3", " ", line)
			n.queue_free()
	quit()
