extends SceneTree
func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	for mission in Array(OS.get_cmdline_user_args()):
		var sm := SimMission.load_mission(data, mission, 1, false)
		var w := sm.world
		var lead: SimUnit = w.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover())[0]
		print(mission, " lead at ", lead.position)
		for gs in w.gates:
			var g: Dictionary = w.map.gates[gs.gate_id]
			var p: SimStructure = gs.parent
			print("  gate %d %s at %.0f,%.0f (%.0f m from lead) placement_team=%d map_team=%d locked=%s parent=%s" % [gs.gate_id, gs.model, gs.position.x, gs.position.y,
				gs.position.distance_to(lead.position), gs.gate_team, g["team"], g["locked"], (p.name + " team " + str(p.team)) if p else "none"])
	quit()
