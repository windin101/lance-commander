extends SceneTree
func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	for mission in Array(OS.get_cmdline_user_args()):
		var sm := SimMission.load_mission(data, mission, 1, true)
		var w := sm.world
		var walls := w.units.filter(func(u): return u is SimStructure and SimWalls.is_wall(u.model) )
		var dead0 := walls.filter(func(u): return u.is_destroyed()).size()
		var dl := {}
		for u in walls:
			dl[u.model + " dl=" + str(u.damage_level)] = dl.get(u.model + " dl=" + str(u.damage_level), 0) + 1
		print(mission, " walls ", walls.size(), " destroyed at t0 ", dead0, " ", dl)
		var n_ev := 0
		for i in 1800:
			w.step(1.0 / 30.0)
			for e in w.events:
				if e.get("type", "") in ["destroyed", "structure_destroyed", "prop_destroyed"]:
					n_ev += 1
			w.events.clear()
		print("   after 60 s: destroyed ", walls.filter(func(u): return u.is_destroyed()).size(), " events ", n_ev)
	quit()
