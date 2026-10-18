extends SceneTree
## Headless autoplay of a mission: the player lance pursues the current objective
## (move to its area, or attack its nearest remaining target). Reports progress.
## godot --headless --path game -s res://tools/autoplay.gd -- [seed] [max_seconds]
## Enemy AI runs the mission's original ABL; the end report lists ABL errors, missing
## natives and where each brain finished.

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var seed_value := int(args[0]) if args.size() > 0 else 1
	var max_t := float(args[1]) if args.size() > 1 else 1800.0
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var sm := SimMission.load_mission(data, "mc2_01", seed_value)
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
		w.events.clear()
		if w.time >= next_order:
			next_order = w.time + 3.0
			_orders(sm)
	var alive := w.units.filter(func(u): return u.team == 0 and u.is_mover() and not u.is_disabled())
	var enemies := w.units.filter(func(u): return u.team != 0 and u.is_mover() and not u.is_disabled())
	print("seed %d end t=%.0f result=%s  player alive %d  enemies alive %d" % [seed_value, w.time,
		["PLAYING", "WON", "LOST"][o.result], alive.size(), enemies.size()])
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
				w.order_attack(m, targets[0])
			elif area != null and m.distance_to(area) > 40.0 and m.order == SimWorld.Order.HOLD:
				w.order_move(m, area)
		return
