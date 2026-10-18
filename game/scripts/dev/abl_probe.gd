extends SceneTree
## Dev probe: run a mission's ABL (the mission script and every unit brain its FIT
## names) for N updates with all game natives missing, then report runtime errors and
## the natives the scripts reached. Usage:
##   godot --headless --path game -s res://scripts/dev/abl_probe.gd -- --mission=mc2_01 --updates=5


func _init() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var mission: String = args.get("mission", "mc2_01")
	var updates := int(args.get("updates", "5"))
	var rt := AblRuntime.new("res://data/abl", 1)
	# Minimal stubs so event loops terminate (PILOT_EVENT_NONE).
	rt.register_native("getNextPilotEvent", func(_i, _a): return -1)
	var insts: Array = []
	insts.append(rt.instantiate(mission + ".abl"))
	var fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % mission)) if FileAccess.file_exists("res://data/missions/%s.json" % mission) else {}
	var brains := {}
	for k in fit:
		if k.begins_with("Warrior") and fit[k] is Dictionary and fit[k].has("Brain"):
			brains[String(fit[k]["Brain"]).to_lower().trim_suffix(".abl")] = true
	if brains.is_empty():  # mission not converted yet: its brains share the mission prefix
		for f in DirAccess.get_files_at("res://data/abl/warriors"):
			if f.begins_with(mission + "_") and f.ends_with(".abl"):
				brains[f.trim_suffix(".abl")] = true
	for b in brains:
		var i := rt.instantiate("warriors/%s.abl" % b)
		if i:
			insts.append(i)
	var t0 := Time.get_ticks_usec()
	for n in updates:
		for i in insts:
			if i:
				i.execute()
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("instances %d, %d updates in %.1f ms (%.2f ms per brain update)" % [insts.size(), updates, ms, ms / maxf(insts.size() * updates, 1)])
	print("errors: ", rt.errors.slice(0, 20))
	var names := rt.unknown.keys()
	names.sort()
	print("natives reached (%d): %s" % [names.size(), " ".join(names)])
	var states := {}
	for i in insts:
		if i and i.unit["kind"] == "fsm":
			states[i.state] = states.get(i.state, 0) + 1
	print("fsm states after run: ", states)
	quit()
