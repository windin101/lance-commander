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
	if args.has("static"):
		_static_natives()
		quit()
		return
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


## Every name the campaign's ABL calls that no script or library declares and that
## isn't a variable or constant: the natives phase 10 must bind. Prints name(count).
func _static_natives() -> void:
	var rt := AblRuntime.new("res://data/abl", 1)
	var counts := {}
	var files := []
	for dir in ["res://data/abl", "res://data/abl/warriors"]:
		for f in DirAccess.get_files_at(dir):
			if f.ends_with(".abl") or f.ends_with(".abx"):
				files.append(dir.path_join(f))
	for path in files:
		var u := rt.load_unit(path)
		if u.has("error"):
			continue
		var known := {}
		for n in u["vars"]:
			known[n] = true
		for n in u["consts"]:
			known[n] = true
		for n in u["routines"]:
			known[n] = true
			for p in u["routines"][n]["params"]:
				known[p["name"]] = true
			for v in u["routines"][n]["vars"]:
				known[v] = true
		var bodies := [u["code"]]
		for n in u["routines"]:
			bodies.append(u["routines"][n]["body"])
		for b in bodies:
			_walk(b, known, rt, counts)
	var names := counts.keys()
	names.sort_custom(func(a, b): return counts[a] > counts[b])
	var out := []
	for n in names:
		out.append("%s(%d)" % [n, counts[n]])
	print("natives (%d): %s" % [names.size(), " ".join(out)])


func _walk(node: Variant, known: Dictionary, rt: AblRuntime, counts: Dictionary) -> void:
	if node is Array:
		for x in node:
			_walk(x, known, rt, counts)
		return
	if not (node is Dictionary):
		return
	var k = node.get("k", "")
	if k in ["call", "fcall", "name"]:
		var n: String = node["name"]
		var std := ["return", "print", "mcprint", "concat", "getstatehandle", "getcurrentstatehandle", "setstate", "resetorders",
			"abs", "sqrt", "round", "trunc", "random", "seedrandom", "setmaxloops", "fileopen", "filewrite", "fileclose",
			"fatal", "assert", "getmodule", "getfunctionhandle", "callfunction", "setflag", "getflag", "true", "false"]
		if not (known.has(n) or rt._global_routines.has(n) or rt._global_consts.has(n) or rt._global_eternals.has(n) or n in std):
			var lib_static := false
			for li in rt._lib_inst.values():
				if li.statics.has(n):
					lib_static = true
			if not lib_static:
				counts[n] = counts.get(n, 0) + 1
	for key in node:
		if key != "k":
			_walk(node[key], known, rt, counts)
