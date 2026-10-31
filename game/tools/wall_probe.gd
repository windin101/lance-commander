extends SceneTree
## Probe: wall and gate cells on the converted maps, and whether a mech can path through a wall line (LANCE-21 walls task).
## godot --headless --path game -s res://tools/wall_probe.gd -- mc2_01 mc2_02 ...

func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var missions := OS.get_cmdline_user_args()
	if missions.is_empty():
		missions = ["mc2_02", "mc2_12", "mc2_24"]
	for mission in missions:
		var sm := SimMission.load_mission(data, mission)
		var map: SimMap = sm.world.map
		var walls := 0; var wall_pass := 0; var gates := 0; var gate_pass := 0
		for i in map.cells.size():
			var c := Vector2i(i % map.cells_per_side, i / map.cells_per_side)
			if map.cell_flag(c, "wall") == 1:
				walls += 1
				wall_pass += map.cell_flag(c, "passable")
			if map.cell_flag(c, "gate") == 1:
				gates += 1
				gate_pass += map.cell_flag(c, "passable")
		print("%s: wall-flag cells %d (passable %d), gate-flag cells %d (passable %d)" % [mission, walls, wall_pass, gates, gate_pass])
		var path := "res://data/maps/%s/objects.json" % mission
		var d: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
		var shown := 0
		var counts := {}
		for o in d["objects"]:
			var t: Dictionary = d["types"].get(str(int(o["type"])), {})
			var app := String(t.get("appearance", ""))
			if not (("wall" in app and "light" in app or "medium" in app or "heavy" in app) or "gate" in app or "post" in app):
				continue
			var pos := Vector2(float(o["x"]), float(o["y"])) * 0.2
			var cell := map.cell_of(pos)
			counts[app] = int(counts.get(app, 0)) + 1
			if shown < 6 and not ("post" in app):
				shown += 1
				var rot := deg_to_rad(float(o["rotation"]))
				var along := Vector2(sin(rot), cos(rot))  # unit along the piece (either sign)
				var across := along.rotated(PI / 2)
				var mid := pos + along * 10.0
				var a := mid + across * 25.0
				var b := mid - across * 25.0
				var p := map.find_path(a, b)
				var plen := 0.0
				for k in range(1, p.size()):
					plen += p[k - 1].distance_to(p[k])
				var cells_pass := 0
				for s in range(-10, 11):
					cells_pass += map.cell_flag(map.cell_of(mid + across * s * 1.0), "passable")
				print("   %-14s class %s dmg %s at cell %s own cell passable=%d wall=%d gate=%d | crossing 50 m line: path %s len %.0f | passable cells in 21 samples across = %d" % [app, str(t.get("class")), str(t.get("damage_level")), str(cell), map.cell_flag(cell, "passable"), map.cell_flag(cell, "wall"), map.cell_flag(cell, "gate"), "none" if p.is_empty() else str(p.size()), plen, cells_pass])
		# footprint check: rasterise the piece (post block + body) and count passable cells
		var fp := {}
		for o in d["objects"]:
			var t2: Dictionary = d["types"].get(str(int(o["type"])), {})
			var ap := String(t2.get("appearance", ""))
			if not ("wall" in ap and ("light" in ap or "medium" in ap or "heavy" in ap)):
				continue
			var p0 := Vector2(float(o["x"]), float(o["y"])) * 0.2
			var rr := deg_to_rad(float(o["rotation"]))
			var al := Vector2(sin(rr), cos(rr))
			var ac := al.rotated(PI / 2)
			var n := 0; var pas := 0
			for zi in range(-10, 18):
				for xi in range(-1, 2):
					var q := p0 + al * float(zi) + ac * float(xi)
					n += 1
					pas += map.cell_flag(map.cell_of(q), "passable")
			var key := ap
			if not fp.has(key):
				fp[key] = [0, 0, 0]
			fp[key][0] += 1; fp[key][1] += n; fp[key][2] += pas
		for k in fp:
			print("   footprint %-14s pieces %d samples %d passable %d (%.0f%%)" % [k, fp[k][0], fp[k][1], fp[k][2], 100.0 * fp[k][2] / fp[k][1]])
		print("   counts: ", counts)
	quit()
