extends SceneTree
## Top-view height map of an original model: one char per CELL m (height in 1.0 m steps: 0-9 then a-z), x to the right, z DOWN the page.
func _init() -> void:
	var cell := 1.2
	for app in Array(OS.get_cmdline_user_args()):
		var n: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		root.add_child(n)
		var hm := {}
		var lo := Vector2(1e9, 1e9); var hi := Vector2(-1e9, -1e9)
		for m in n.find_children("*", "MeshInstance3D", true, false):
			var mi := m as MeshInstance3D
			if mi.name.to_lower().begins_with("litwin"): continue
			var xf: Transform3D = n.global_transform.affine_inverse() * mi.global_transform
			for s in mi.mesh.get_surface_count():
				var arr := mi.mesh.surface_get_arrays(s)
				var V: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]; var I: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
				for t in range(0, I.size(), 3):
					var a := xf * V[I[t]]; var b := xf * V[I[t + 1]]; var c := xf * V[I[t + 2]]
					var area := ((b - a).cross(c - a)).length() * 0.5
					var k := int(clampf(area / (cell * cell * 0.3), 1, 400))
					for i in k:
						var u := randf(); var v := randf()
						if u + v > 1.0: u = 1.0 - u; v = 1.0 - v
						var p := a + (b - a) * u + (c - a) * v
						var key := Vector2i(int(floor(p.x / cell)), int(floor(p.z / cell)))
						hm[key] = maxf(hm.get(key, -9.0), p.y)
						lo.x = minf(lo.x, key.x); lo.y = minf(lo.y, key.y); hi.x = maxf(hi.x, key.x); hi.y = maxf(hi.y, key.y)
		print("TOP == ", app, " cell ", cell, " x0 ", lo.x * cell, " z0 ", lo.y * cell, " (rows = z, cols = x; char = height m)")
		for z in range(int(lo.y), int(hi.y) + 1):
			var row := ""
			for x in range(int(lo.x), int(hi.x) + 1):
				var h: float = hm.get(Vector2i(x, z), -99.0)
				if h < -50.0: row += " "
				else:
					var q := int(round(maxf(h, 0.0)))
					row += str(q) if q < 10 else char(87 + q)
			print("TOP ", row)
	quit()
