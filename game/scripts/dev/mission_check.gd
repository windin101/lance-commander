extends SceneTree
## Dev check: load each converted campaign mission in the sim and report what doesn't
## resolve: skipped parts, unsupported objective conditions, ABL errors and missing
## natives after a short run.
##   godot --headless --path game -s res://scripts/dev/mission_check.gd -- [mc2_02 ...] [--seconds=20]


func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var names: Array = []
	var seconds := 20.0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--seconds="):
			seconds = float(a.split("=")[1])
		elif not a.begins_with("--"):
			names.append(a)
	if names.is_empty():
		for i in range(1, 25):
			names.append("mc2_%02d" % i)
	for m in names:
		if not FileAccess.file_exists("res://data/missions/%s.json" % m):
			print("%s: not converted" % m)
			continue
		var t0 := Time.get_ticks_msec()
		var sm := SimMission.load_mission(data, m, 1)
		var load_ms := Time.get_ticks_msec() - t0
		var movers := sm.world.units.filter(func(u): return u.is_mover())
		var no_id := movers.filter(func(u): return u.part_id == 0).size()
		t0 = Time.get_ticks_msec()
		for i in int(seconds / SimWorld.TICK):
			sm.step()
			sm.world.events.clear()
		var run_ms := Time.get_ticks_msec() - t0
		var rt: AblRuntime = sm.abl.runtime if sm.abl else null
		var unk: Array = rt.unknown.keys() if rt else []
		unk.sort()
		print("%s: movers %d (no part id %d) pilots %d skipped %s | objectives %d unsupported %s | abl errors %s missing %s | load %d ms, %ds sim in %d ms" % [
			m, movers.size(), no_id, sm.abl.pilots.size() if sm.abl else 0, _counts(sm.skipped),
			sm.objectives.objectives.size(), "%s dropped %d" % [sm.objectives.unsupported, sm.objectives.dropped], (rt.errors.slice(0, 3) if rt else "no abl"), unk,
			load_ms, int(seconds), run_ms])
	data.free()
	quit()


func _counts(list: Array) -> Dictionary:
	var c := {}
	for x in list:
		c[x] = c.get(x, 0) + 1
	return c
