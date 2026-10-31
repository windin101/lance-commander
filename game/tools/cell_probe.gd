extends SceneTree
## godot --headless --path game -s res://tools/cell_probe.gd -- mc2_14 661 90 [--no-walls]
func _init() -> void:
	var a := Array(OS.get_cmdline_user_args()).filter(func(x): return not x.begins_with("--"))
	SimMission.use_walls = not ("--no-walls" in OS.get_cmdline_user_args())
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var sm := SimMission.load_mission(data, a[0], 1, true)
	var m: SimMap = sm.world.map
	var c := m.cell_of(Vector2(float(a[1]), float(a[2])))
	for dy in range(-4, 5):
		var row := ""
		for dx in range(-6, 7):
			var cc := c + Vector2i(dx, dy)
			var ch := "."
			if not m.is_walkable(cc, false): ch = "#"
			if m.gate_cells.has(cc): ch = "g"
			if cc == c: ch = "T" if ch == "." else "X"
			row += ch
		print("ROW ", row)
	print("stamped by walls: ", m._stamped.has(c) if "_stamped" in m else "?", " walkable ", m.is_walkable(c, false))
	quit()
