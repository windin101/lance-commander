extends SceneTree
## Headless autoplay of a mission: the player lance pursues the current objective
## (move to its area, or attack its nearest remaining target). Reports progress.
## godot --headless --path game -s res://tools/autoplay.gd -- [seed] [max_seconds] [--mission=mc2_NN] [--cues]
## Enemy AI runs the mission's original ABL; the end report lists ABL errors, missing
## natives and where each brain finished.

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var seed_value := int(args[0]) if args.size() > 0 else 1
	var max_t := float(args[1]) if args.size() > 1 else 1800.0
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var mission := "mc2_01"
	for a in args:
		if a.begins_with("--mission="):
			mission = a.split("=")[1]
	var sm := SimMission.load_mission(data, mission, seed_value)
	print("mission %s" % mission)
	print("ABL pilots: %d" % (sm.abl.pilots.size() if sm.abl else 0))
	var w := sm.world
	var o := sm.objectives
	var next_order := 0.0
	for u in w.units:
		_start[u.id] = u.position
	while w.time < max_t and o.result == SimObjectives.Result.PLAYING:
		sm.step()
		for e in w.events:
			match e["type"]:
				"objective":
					if not e["hidden"]:
						print("t=%6.1f  objective done: %s" % [w.time, e["title"]])
				"disabled":
					var u: SimUnit = w.units[e["unit"]]
					if u.team == 0:
						print("t=%6.1f  LOST %s" % [w.time, u.name])
				"mission_end":
					print("t=%6.1f  MISSION %s" % [w.time, "WON" if e["won"] else "LOST"])
				"abl_wave", "abl_video", "abl_music":
					if "--cues" in args:
						print("t=%6.1f  %s %s" % [w.time, e["type"], e.get("file", e.get("id", ""))])
		w.events.clear()
		if w.time >= next_order:
			next_order = w.time + 3.0
			_orders(sm)
	var alive := w.units.filter(func(u): return u.team == 0 and u.is_mover() and not u.is_disabled())
	var enemies := w.units.filter(func(u): return u.team != 0 and u.is_mover() and not u.is_disabled())
	print("seed %d end t=%.0f result=%s  player alive %d  enemies alive %d" % [seed_value, w.time,
		["PLAYING", "WON", "LOST"][o.result], alive.size(), enemies.size()])
	for obj in o.objectives:
		var state: String = ["open", "done", "FAILED"][int(obj["status"])]
		if not obj["active"]:
			state = "inactive (flag %s)" % obj["activate_flag"]
		elif obj["status"] == 0 and not o.is_active(obj):
			state = "gated"
		print("  obj %d %s%s: %s  %s" % [obj["index"], "P" if obj["primary"] else "s", " hidden" if obj["hidden"] else "", state,
			String(obj["title"]).strip_edges().left(48)])
		if "--targets" in args and obj["status"] == 0 and obj["active"]:
			var lead: SimUnit = null
			for u in w.units:
				if u.team == 0 and u.commander == 0 and u.is_mover() and not u.is_disabled():
					lead = u
					break
			for c in obj["conditions"]:
				var t: SimUnit = c.get("unit")
				if t == null or t.is_disabled():
					continue
				var path_n := w.map.find_path(lead.position, w.map.nearest_walkable(t.position, lead.hover), lead.hover).size() if lead else -1
				print("      %s exists=%s awake=%s team=%d dist=%.0f path=%d brain=%s" % [t.name, t.exists, t.awake, t.team,
					lead.position.distance_to(t.position) if lead else -1.0, path_n,
					(t.brain.inst.state if t.brain is SimAbl.Pilot and t.brain.inst.unit["kind"] == "fsm" else "-")])
	if sm.abl:
		var rt := sm.abl.runtime
		print("abl errors: ", rt.errors.slice(0, 8))
		var unk := rt.unknown.keys()
		unk.sort()
		print("abl natives missing: ", unk)
		var states := {}
		for p in sm.abl.pilots:
			var key := "%s:%s" % [p.unit.brain_name, p.inst.state]
			states[key] = states.get(key, 0) + 1
		print("brain end states: ", states)
		var moved := 0
		for p in sm.abl.pilots:
			if p.unit.position.distance_to(_start.get(p.unit.id, p.unit.position)) > 20.0:
				moved += 1
		print("enemy pilots that moved >20 m: %d / %d" % [moved, sm.abl.pilots.size()])
	data.free()
	quit()


var _start := {}


func _orders(sm: SimMission) -> void:
	var w := sm.world
	var lance := w.units.filter(func(u): return u.team == 0 and u.is_mover() and not u.is_disabled())
	for obj in sm.objectives.objectives:
		if obj["hidden"] or not sm.objectives.is_active(obj):
			continue
		var targets := []
		var area = null
		for c in obj["conditions"]:
			if c.has("unit") and c["unit"] and not c["unit"].is_disabled():
				targets.append(c["unit"])
			elif c.has("center"):
				area = c["center"]
		for m in lance:
			if m.order == SimWorld.Order.ATTACK and m.order_target and not m.order_target.is_disabled():
				continue  # keep fighting (incl. return fire)
			if not targets.is_empty():
				targets.sort_custom(func(a, b): return m.distance_to(a.position) < m.distance_to(b.position))
				var t: SimUnit = targets[0]
				if sm.abl and sm.abl.can_capture(t, 0) and m is SimMech:
					var near := _near_enemies(w, t.position)
					if near.is_empty():
						if not (m.brain is SimAbl.Pilot and int(m.brain.order["code"]) == SimAbl.TO_CAPTURE):
							_order(sm, m, "capture", t)
					else:
						_order(sm, m, "attack", near[0])  # clear the defenders first
				else:
					_order(sm, m, "attack", t)
			elif area != null and not _near_enemies(w, area).is_empty():
				# Extraction needs the area clear of other commanders' units (256 m): clear it.
				var near := _near_enemies(w, area)
				near.sort_custom(func(a, b): return m.distance_to(a.position) < m.distance_to(b.position))
				_order(sm, m, "attack", near[0])
			elif area != null and m.distance_to(area) > 40.0 and m.order == SimWorld.Order.HOLD:
				_order(sm, m, "move", area)
		return


## Orders go through the lance's pbrain, as the player's do (CommandInput).
func _order(sm: SimMission, m: SimUnit, kind: String, arg: Variant) -> void:
	if sm.abl and m.brain is SimAbl.Pilot:
		sm.abl.player_order(m, kind, arg)
	elif kind == "attack":
		sm.world.order_attack(m, arg)
	else:
		sm.world.order_move(m, arg)


func _near_enemies(w: SimWorld, area: Vector2) -> Array:
	return w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists and not u.is_disabled() \
		and not u.hulk and u.position.distance_to(area) <= 300.0)
