extends SceneTree
## Capturable structures the lance can walk to (gates all treated open) -- run with and without --no-walls and diff.
func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	SimMission.use_walls = not ("--no-walls" in OS.get_cmdline_user_args())
	for mission in Array(OS.get_cmdline_user_args()).filter(func(a): return not a.begins_with("--")):
		var sm := SimMission.load_mission(data, mission, 1, true)
		var w := sm.world
		var lead: SimUnit = w.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover() and not u.hover)[0]
		for u in w.units:
			if u is SimStructure and u.capturable and sm.abl:
				var g: Vector2 = sm.abl._capture_goal(lead, u)
				var ok := not w.map.find_path(lead.position, g, false, false, SimMap.ALL_OPEN).is_empty()
				print("REACH %s %s %.0f,%.0f %s" % [mission, u.name, u.position.x, u.position.y, ok])
	quit()
