extends SceneTree

func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var sm := SimMission.load_mission(data, "mc2_01", 11)
	var w := sm.world
	var pat: SimUnit = w.units.filter(func(u): return u.brain_name == "mc2_01_Pat4")[0]
	var mech: SimUnit = w.units.filter(func(u): return u.brain_name == "PBrain")[0]
	mech.position = sm.objectives.objectives[0]["conditions"][0]["center"]
	print("patrol pts ", pat.brain.patrol, " start ", pat.position, " hover ", pat.hover)
	for p in pat.brain.patrol:
		print("  pt ", p, " walkable(hover) ", w.map.is_walkable(w.map.cell_of(p), true), " nearest ", w.map.nearest_walkable(p, true))
	for i in 250:
		sm.step()
		if i % 10 == 0:
			print("t=%4.1f pos=(%d,%d) state=%s order=%d path=%d idx=%d issued=%d speed=%.1f status=%d" % [w.time, pat.position.x, pat.position.y, pat.brain.state, pat.order, pat.path.size(), pat.brain.patrol_index, pat.brain._patrol_issued, pat.speed, pat.status])
		w.events.clear()
	data.free()
	quit()
