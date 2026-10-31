extends SceneTree
## Reachability of every objective with walls on (LANCE-21 step 3): from the player's drop, can team 0 walk to each
## objective's unit or area? If not, which enemy gate(s), destroyed or captured (= open for team 0), would open it?
## godot --headless --path game -s res://tools/wall_reach.gd -- mc2_11 mc2_14 ...  (no args: every mission with walls)

func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var missions := Array(OS.get_cmdline_user_args()).filter(func(a): return not a.begins_with("--"))
	SimMission.use_walls = not ("--no-walls" in OS.get_cmdline_user_args())
	if missions.is_empty():
		for n in range(1, 25):
			missions.append("mc2_%02d" % n)
	var bad := 0
	for mission in missions:
		var sm := SimMission.load_mission(data, mission, 1, false)
		var w := sm.world
		var map: SimMap = w.map
		var lead: SimUnit = null
		for u in w.units:
			if u.team == 0 and u.commander == 0 and u.is_mover() and not u.hover and not u.flying:
				lead = u
				break
		if lead == null:
			continue
		var closed := 0
		for id in map.gates:
			if not map.gate_passable(id, 0):
				closed += 1
		var bad_targets := []
		var n_targets := 0
		for obj in sm.objectives.objectives:
			if not obj["primary"]:
				continue
			for c in obj["conditions"]:
				var goals := []
				var t: SimUnit = c.get("unit")
				if t != null:
					goals.append(map.nearest_walkable(t.position, false))
					if t.capturable and sm.abl:
						goals.append(sm.abl._capture_goal(lead, t))
				elif c.has("center"):
					goals.append(map.nearest_walkable(c["center"], false))
				if goals.is_empty():
					continue
				n_targets += 1
				var ok := goals.any(func(g): return not map.find_path(lead.position, g, false, false, 0).is_empty())
				if ok:
					continue
				# which single gate opens it?
				var fixes := []
				for id in map.gates.keys():
					if map.gate_passable(id, 0):
						continue
					var keep: Dictionary = map.gates[id].duplicate()
					map.set_gate(id, -1, false, true)
					if goals.any(func(g): return not map.find_path(lead.position, g, false, false, 0).is_empty()):
						fixes.append(id)
					map.set_gate(id, keep["team"], keep["locked"], keep["destroyed"])
				# capture a gate control building (its gates then open for team 0, gate.cpp:170-205)
				var parents := {}
				for gs in w.gates:
					if gs.parent != null:
						parents[gs.parent] = true
				var cap_fixes := []
				for par in parents:
					var saved_g := {}
					for gs in w.gates:
						if gs.parent == par:
							saved_g[gs.gate_id] = map.gates[gs.gate_id].duplicate()
							map.set_gate(gs.gate_id, 0, false, false)
					if goals.any(func(g): return not map.find_path(lead.position, g, false, false, 0).is_empty()):
						var gp: Vector2 = sm.abl._capture_goal(lead, par) if sm.abl else par.position
						var reach := not map.find_path(lead.position, gp, false, false, 0).is_empty()
						cap_fixes.append("%s(capturable=%s, reachable now=%s, %d gates)" % [par.name, par.capturable, reach, saved_g.size()])
					for id in saved_g:
						map.set_gate(id, saved_g[id]["team"], saved_g[id]["locked"], saved_g[id]["destroyed"])
				if not cap_fixes.is_empty():
					fixes.append("CAPTURE " + ", ".join(cap_fixes))
				# and with every gate open (destroyed)?
				var saved := {}
				for id in map.gates.keys():
					saved[id] = map.gates[id].duplicate()
					map.set_gate(id, -1, false, true)
				var all_open := goals.any(func(g): return not map.find_path(lead.position, g, false, false, 0).is_empty())
				for id in saved:
					map.set_gate(id, saved[id]["team"], saved[id]["locked"], saved[id]["destroyed"])
				if not all_open:
					fixes.append("ALL-OPEN-STILL-BLOCKED")
				bad_targets.append("%s %s obj %d: no path; single gates that open it: %s" % [c["kind"], (t.name if t else "area"), int(obj["index"]), str(fixes)])
		print("%s gates %d (closed to team 0: %d) primary targets %d unreachable %d" % [mission, map.gates.size(), closed, n_targets, bad_targets.size()])
		for b in bad_targets:
			print("    ", b)
			bad += 1
	print("UNREACHABLE TOTAL ", bad)
	quit()
