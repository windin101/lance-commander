extends SceneTree
## Headless mission probe: spawn mc2_01, report paths to each enemy, run a demo battle.
## godot --headless --path game -s res://tools/sim_probe.gd -- [seconds]

func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var sm := SimMission.load_mission(data, "mc2_01")
	var w := sm.world
	var me := w.units[0]
	for e in w.units:
		if e.team == me.team:
			continue
		var goal := w.map.nearest_walkable(e.position)
		var path := w.map.find_path(me.position, goal)
		var length := 0.0
		for i in range(1, path.size()):
			length += path[i - 1].distance_to(path[i])
		print("%-11s at (%5.0f,%5.0f) dist %5.0f  path pts %4d  len %5.0f  goal-walkable %s" % [e.name, e.position.x, e.position.y,
			me.distance_to(e.position), path.size(), length, w.map.is_walkable(w.map.cell_of(e.position))])
	for m in w.units:
		if m.team != me.team:
			continue
		var best: SimMech = null
		for e in w.enemies_of(m):
			if best == null or m.distance_to(e.position) < m.distance_to(best.position):
				best = e
		w.order_attack(m, best)
	var secs := float(OS.get_cmdline_user_args()[0]) if OS.get_cmdline_user_args().size() > 0 else 120.0
	var t := 0.0
	var shots := 0
	while t < secs:
		w.step()
		t += SimWorld.TICK
		for e in w.events:
			if e["type"] == "shot":
				shots += 1
			elif e["type"] == "disabled":
				print("t=%5.1f  %s disabled%s" % [t, w.units[e["unit"]].name, " (destroyed)" if e["destroyed"] else ""])
		w.events.clear()
		if int(t * 10) % 200 == 0:
			var line := "t=%5.1f" % t
			for m in w.units:
				line += "  %s(%d,%d %s)" % [m.name.left(4), m.position.x, m.position.y, ["ok", "sd", "dis", "dead"][m.status]]
			print(line)
	print("shots fired: ", shots)
	data.free()
	quit()
