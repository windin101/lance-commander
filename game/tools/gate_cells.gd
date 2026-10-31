extends SceneTree
func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	for mission in Array(OS.get_cmdline_user_args()):
		var sm := SimMission.load_mission(data, mission, 1, true)
		var m: SimMap = sm.world.map
		var np := 0
		for c in m.gate_cells:
			if m.cell_flag(c, "passable") == 0:
				np += 1
		print("GC ", mission, " gate cells ", m.gate_cells.size(), " impassable base bit ", np)
		var lead: SimUnit = sm.world.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover())[0]
		var p := Vector2(-804, -1119)
		var c0 := m.cell_of(p)
		print("GC lance pocket: walkable ", m.is_walkable(c0, false))
		for dy in range(-6, 7):
			var row := ""
			for dx in range(-10, 11):
				var cc := c0 + Vector2i(dx, dy)
				var ch := "."
				if not m.is_walkable(cc, false): ch = "#"
				if m.gate_cells.has(cc): ch = "g" if m.cell_flag(cc, "passable") == 1 else "G"
				if cc == c0: ch = "@"
				row += ch
			print("GC ", row)
	quit()
