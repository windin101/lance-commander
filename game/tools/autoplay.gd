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
					if u.capturable and u.team != 0:
						print("t=%6.1f  capture target %s destroyed by %s" % [w.time, u.name, u.last_attacker.name if u.last_attacker else "?"])
					if u.team == 0:
						var arm := 0.0
						var top := 0.0
						for i in u.armor.size():
							arm += u.armor[i]
							top += u.max_armor[i]
						print("t=%6.1f  LOST %s (%s, armour %.0f%%, heat %.0f, ejected %s, pilot %s, last hit by %s)" % [w.time, u.name,
							["normal", "shutdown", "disabled", "destroyed"][u.status], 100.0 * arm / maxf(top, 1.0), u.heat, u.ejected,
							u.pilot.status_text() if u.pilot and u.pilot.has_method("status_text") else (str(u.pilot.wounds) + " wounds" if u.pilot else "-"),
							u.last_attacker.name if u.last_attacker else "-"])
				"mission_end":
					print("t=%6.1f  MISSION %s" % [w.time, "WON" if e["won"] else "LOST"])
				"impact":
					var victim: SimUnit = w.units[e["unit"]]
					if victim.team == 0 and victim.commander == 0 and int(e.get("from", -1)) >= 0:
						var src: SimUnit = w.units[e["from"]]
						var key := "%s (%s)" % [src.name, "mech" if src is SimMech else "vehicle"]
						_damage[key] = _damage.get(key, 0.0) + float(e.get("damage", 0.0))
						_attackers[src.id] = true
						var loc := int(e.get("location", -1))
						_locs[loc] = _locs.get(loc, 0) + 1
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
	if "--damage" in args:
		var keys := _damage.keys()
		keys.sort_custom(func(a, b): return _damage[a] > _damage[b])
		var total := 0.0
		for k in keys:
			total += _damage[k]
		print("damage to lance: %.0f from %d attackers; hits by location (0 head .. 10 rear RT): %s" % [total, _attackers.size(), _locs])
		for k in keys.slice(0, 10):
			print("    %6.0f  %s" % [_damage[k], k])
	for obj in o.objectives:
		var state: String = ["open", "done", "FAILED"][int(obj["status"])]
		if not obj["active"]:
			state = "inactive (flag %s)" % obj["activate_flag"]
		elif obj["status"] == 0 and not o.is_active(obj):
			state = "gated"
		print("  obj %d %s%s: %s  %s" % [obj["index"], "P" if obj["primary"] else "s", " hidden" if obj["hidden"] else "", state,
			String(obj["title"]).strip_edges().left(48)])
		if "--targets" in args and obj["status"] == 0 and obj["active"]:
			for c in obj["conditions"]:
				if c["kind"] == "MoveAllSurvivingMechsToArea":
					for u in w.units:
						if u.is_mover() and u.exists and u.commander != 0 and not SimObjectives.dead(u) and not u.hulk \
								and u.position.distance_to(c["center"]) <= SimObjectives.EXTRACT_CLEAR_M:
							print("      extraction blocked by %s (team %d, commander %d, brain %s, %.0f m)" % [u.name, u.team, u.commander,
								u.brain_name, u.position.distance_to(c["center"])])
					for u in w.units:
						if u.is_mover() and u.team == 0 and u.commander == 0 and u is SimMech and not SimObjectives.dead(u) and not u.hulk:
							print("      lance %s %.0f m from the point (radius %.0f), path %d, order %d" % [u.name,
								u.position.distance_to(c["center"]), c["radius"],
								w.map.find_path(u.position, w.map.nearest_walkable(c["center"], u.hover), u.hover).size(), u.order])
							if u.order_target:
								var t: SimUnit = u.order_target
								print("        target %s team %d at %.0f m, awake %s, exists %s, hover %s, path from it %d" % [t.name, t.team,
									u.position.distance_to(t.position), t.awake, t.exists, t.hover,
									w.map.find_path(u.position, w.map.nearest_walkable(t.position, u.hover), u.hover).size()])
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
				var cap := ""
				if t.capturable and sm.abl and lead:
					var b := sm.abl.capture_blocker(t, lead, true)
					cap = " capturable can=%s blocker=%s goal_path=%d" % [sm.abl.can_capture(t, 0), (b.name + "@%.0f" % b.position.distance_to(t.position)) if b else "-",
						w.map.find_path(lead.position, sm.abl._capture_goal(lead, t), lead.hover).size()]
				print("      %s exists=%s awake=%s team=%d dist=%.0f path=%d brain=%s%s" % [t.name, t.exists, t.awake, t.team,
					lead.position.distance_to(t.position) if lead else -1.0, path_n,
					(t.brain.inst.state if t.brain is SimAbl.Pilot and t.brain.inst.unit["kind"] == "fsm" else "-"), cap])
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
var _damage := {}  # attacker "name (kind)" -> damage dealt to the player's lance
var _attackers := {}
var _locs := {}  # armour location -> hits on the lance


const ENGAGE_M := 320.0  # armed enemies this close to the lance are fought before anything else


## A methodical player: fight whatever armed enemy is near the lance first, all on the
## same target; otherwise work the first active objective as a group.
func _orders(sm: SimMission) -> void:
	var w := sm.world
	var lance := w.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover() \
		and u.exists and not u.is_disabled() and not u.hulk and u.refit_pool <= 0.0)
	if lance.is_empty():
		return
	var centre := Vector2.ZERO
	for m in lance:
		centre += m.position
	centre /= lance.size()
	for m in lance:  # don't chase a runner (e.g. a hovercraft over water) across the map
		if m.order == SimWorld.Order.ATTACK and m.order_target and m.distance_to(m.order_target.position) > ENGAGE_M * 1.5:
			_order(sm, m, "stop", null)
	var threats := w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists and u.awake \
		and not u.is_disabled() and not u.hulk and u.num_weapons > 0 \
		and lance.any(func(m): return m.distance_to(u.position) <= ENGAGE_M))
	_use_support(sm, lance, centre, threats)
	if not threats.is_empty():
		threats.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
		var focus: SimUnit = threats[0]
		for m in lance:
			var busy: bool = m.order == SimWorld.Order.ATTACK and m.order_target != null \
				and not m.order_target.is_disabled() and threats.has(m.order_target) \
				and m.distance_to(m.order_target.position) <= ENGAGE_M * 1.5
			if not busy:
				_order(sm, m, "attack", focus)
		return
	for obj in sm.objectives.objectives:
		if obj["hidden"] or not sm.objectives.is_active(obj):
			continue
		var targets := []
		var area = null
		for c in obj["conditions"]:
			if c["kind"] in ["DestroyAllEnemyUnits", "DestroyNumberOfEnemyUnits"]:
				targets.append_array(w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists and u.awake \
					and not u.is_disabled() and not u.hulk))
			elif c.has("unit") and c["unit"] and not c["unit"].is_disabled() and c["unit"].team != 0:
				targets.append(c["unit"])  # already ours (e.g. mc2_06 "protect" = capture own HQ): leave it
			elif c.has("center"):
				area = c["center"]
		if targets.is_empty() and area == null:
			continue  # nothing to do for this one: next objective
		if not targets.is_empty():
			targets.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
			var t: SimUnit = targets[0]
			var capture: bool = sm.abl != null and sm.abl.can_capture(t, 0)
			if capture:
				# Clear the guards first: an armed enemy within 75 m of the target refuses capture.
				var guards := w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists and u.awake \
					and not u.is_disabled() and not u.hulk and u.num_weapons > 0 and u != t \
					and u.position.distance_to(t.position) <= SimAbl.BLOCK_CAPTURE_M + 10.0)
				if not guards.is_empty():
					guards.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
					for m in lance:
						if not (m.order == SimWorld.Order.ATTACK and guards.has(m.order_target)):
							_order(sm, m, "attack", guards[0])
					return
			for m in lance:
				if capture and m is SimMech:
					if not (m.brain is SimAbl.Pilot and int(m.brain.order["code"]) == SimAbl.TO_CAPTURE):
						_order(sm, m, "capture", t)
				elif not capture and not (m.order == SimWorld.Order.ATTACK and m.order_target == t):
					_order(sm, m, "attack", t)
				elif capture and m.distance_to(t.position) > 60.0 and m.order == SimWorld.Order.HOLD:
					_order(sm, m, "move", t.position)  # vehicles escort the capture
		elif not _near_enemies(w, area).is_empty():
			# Extraction needs the area clear of other commanders' units (256 m): clear it.
			var near := _near_enemies(w, area)
			near.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
			for m in lance:
				_order(sm, m, "attack", near[0])
		else:
			for i in lance.size():
				var m: SimUnit = lance[i]
				var spot: Vector2 = area + Vector2.from_angle(TAU * i / lance.size()) * 18.0
				if m.distance_to(spot) > 40.0 and m.order == SimWorld.Order.HOLD:
					_order(sm, m, "move", spot)
		return


## Orders go through the lance's pbrain, as the player's do (CommandInput).
func _order(sm: SimMission, m: SimUnit, kind: String, arg: Variant) -> void:
	if sm.abl and m.brain is SimAbl.Pilot:
		sm.abl.player_order(m, kind, arg)
	elif kind == "attack":
		sm.world.order_attack(m, arg)
	elif kind == "stop":
		sm.world.order_hold(m)
	else:
		sm.world.order_move(m, arg)


func _near_enemies(w: SimWorld, area: Vector2) -> Array:
	return w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists and not u.is_disabled() \
		and not u.hulk and u.position.distance_to(area) <= 300.0)


## Support powers the way a player would use them: salvage disabled enemy mechs near
## the lance, strike bunched enemies away from our own units, call a repair truck in a
## lull when the lance is badly damaged and set it to work.
func _use_support(sm: SimMission, lance: Array, centre: Vector2, threats: Array) -> void:
	var s: SimSupport = sm.support
	var w := sm.world
	if s == null:
		return
	for t in w.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0 and not u.is_disabled()):
		if not s.repairs.any(func(r): return r["truck"] == t):
			var worst: SimUnit = null
			for m in lance:
				if m is SimMech and SimSupport.needs_refit(m) and (worst == null or _armour_frac(m) < _armour_frac(worst)):
					worst = m
			if worst and threats.is_empty():
				s.order_repair(t, worst)
	if s.can_call("salvage_craft"):
		for u in w.units:
			if u is SimMech and u.team != 0 and u.is_disabled() and not u.is_destroyed() and u.exists \
					and u.position.distance_to(centre) <= 400.0:
				if s.call_power("salvage_craft", u):
					return
	if s.can_call("air_strike") and threats.size() >= 2:
		for t in threats:
			var bunch := threats.filter(func(o): return o.position.distance_to(t.position) <= 30.0).size()
			var ours := w.units.filter(func(o): return o.team == 0 and o.is_mover() and not o.is_disabled() \
				and o.position.distance_to(t.position) <= 60.0).size()
			if bunch >= 2 and ours == 0:
				s.call_power("air_strike", t.position)
				return
	if s.can_call("repair_truck") and threats.is_empty():
		var hurt := lance.filter(func(m): return m is SimMech and _armour_frac(m) < 0.5)
		var have_truck := w.units.any(func(u): return u.refit_pool > 0.0 and u.team == 0 and not u.is_disabled())
		if not hurt.is_empty() and not have_truck:
			s.call_power("repair_truck", w.map.nearest_walkable(centre + Vector2(25, 0)))


func _armour_frac(m: SimUnit) -> float:
	var a := 0.0
	var b := 0.0
	for i in m.armor.size():
		a += m.armor[i]
		b += m.max_armor[i]
	return a / maxf(b, 1.0)
