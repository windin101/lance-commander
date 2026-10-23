extends SceneTree
## Headless autoplay of a mission by a methodical player bot. Reports progress.
## godot --headless --path game -s res://tools/autoplay.gd -- [seed] [max_seconds] [--mission=mc2_NN]
##     [--fit-lance] [--damage] [--targets] [--cues] [--shots=N] [--campaign]
## Force: what a campaign player would field on the mission (_player_force: the drop weight
## and 12 slots filled from the purchase lists), or --fit-lance for the mission's own parts.
## Play (_orders): the lance moves as a group, works the primary objectives in order
## (targets, captures, MoveAnyUnitToArea markers, extraction with the area cleared), focus-fires
## the most dangerous and most damaged threats, pulls badly damaged mechs back to a repair truck,
## and uses the support powers (salvage craft, air strike, repair truck, sensor probe).
## Enemy AI runs the mission's original ABL; the end report lists ABL errors, missing
## natives and where each brain finished.

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var seed_value := int(args[0]) if args.size() > 0 else 1
	var max_t := float(args[1]) if args.size() > 1 else 1800.0
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	if "--campaign" in args:
		_campaign(data, max_t)
		data.free()
		quit()
		return
	var mission := "mc2_01"
	for a in args:
		if a.begins_with("--mission="):
			mission = a.split("=")[1]
	var force: Array = [] if "--fit-lance" in args else _player_force(data, mission)
	var sm := SimMission.load_mission(data, mission, seed_value, true, force)
	print("mission %s" % mission)
	print("force: %s" % _force_text(sm, force))
	print("ABL pilots: %d" % (sm.abl.pilots.size() if sm.abl else 0))
	var w := sm.world
	var o := sm.objectives
	for u in w.units:
		_start[u.id] = u.position
	_play(sm, max_t, args, true)
	var alive := w.units.filter(func(u): return u.team == 0 and u.is_mover() and not u.is_disabled())
	var enemies := w.units.filter(func(u): return u.team != 0 and u.is_mover() and not u.is_disabled())
	print("seed %d end t=%.0f result=%s  player alive %d  enemies alive %d" % [seed_value, w.time,
		"LOST" if _lance_gone else ["PLAYING", "WON", "LOST"][o.result], alive.size(), enemies.size()])
	if "--damage" in args:
		var keys := _damage.keys()
		keys.sort_custom(func(a, b): return _damage[a] > _damage[b])
		var total := 0.0
		for k in keys:
			total += _damage[k]
		print("damage to lance: %.0f from %d attackers; hits by location (0 head .. 10 rear RT): %s" % [total, _attackers.size(), _locs])
		var kills := 0
		for k in sm.kills:
			if sm.world.units[k].commander == 0 and sm.world.units[k].team == 0:
				kills += sm.kills[k].size()
		print("damage by lance: %.0f; kills %d" % [_dealt, kills])
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
						if u.is_mover() and u.team == 0 and u.commander == 0 and u is SimMech and not SimObjectives.dead(u) and not u.hulk and u.on_gui:
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
var _shots_left := 0
var _attackers := {}
var _locs := {}  # armour location -> hits on the lance
var _dealt := 0.0  # damage the lance dealt to enemies
var _goal := {}  # unit id -> the move goal the bot last gave it
var _cap_stall := {}  # unit id -> checks it stood still on a capture order
var _stuck := {}  # unit id -> moves to the same goal that left it standing
var _retreat := {}  # unit id -> true while it is pulled back to repair
var _verbose := true
var _last_strike := -INF
var _trace := false  # --trace: print each change of the bot's job
var _last_task := ""


const ENGAGE_M := 320.0  # armed enemies this close to the lance are fought before anything else
const GROUP_M := 90.0  # a mech this much nearer the goal than the lance centre waits for the rest
const RETREAT_FRAC := 0.3  # health share under which a mech pulls back while others fight
const RESUME_FRAC := 0.7  # ... and above which it rejoins
const LEASH_M := 160.0  # in a fight, a mech this far from the rest regroups first
const KILL_TIME := 12.0  # focus fire: enough guns on a target to strip it in about this long
const STRIKE_GUARD_M := 70.0  # no air strike this close to our own units or a target we must keep


# --- the force -------------------------------------------------------------------------

## What a campaign player would field on this mission (campaign-layer.md 3, 5, 8, 9) in place
## of the FIT's own player parts (3.4), so the sweep measures the mission, not a placeholder lance:
## - mc2_01 (PlayLogistics 0): the mission's own parts, as the game plays it ([] here).
## - C-Bills: 80000 + the starting lance's value (sell-back is 100%, 5.2) + the primary
##   objective payouts of every earlier campaign mission (9); no losses, no salvage income.
## - On sale: the chassis of this and every earlier purchase file (a mech bought earlier is
##   still owned; components only accumulate, 10.3) and the PurBonus files of earlier missions.
## - Fill the drop weight with a lance of heavies: about one mech per 60 t of the limit (1-8
##   mechs here, 12 at most), each the heaviest affordable chassis within 15 t of an even share
##   of the weight left, in its dearest affordable variant (the most weapons).
## - Pilots: the best available by gunnery + piloting, each grown by +1 piloting and +2 gunnery
##   per earlier mission (8.3: +1 piloting per win, kills up to +4 gunnery), capped at 80.
func _player_force(data: Object, mission: String) -> Array:
	var camp := Campaign.create(data)
	if not camp.plays_logistics(mission):
		return []
	var order := _campaign_order()
	var at := order.find(mission)
	if at < 0:
		return []
	var cbills := float(Campaign.START_CBILLS)
	for p in [["werewolf", 0], ["bushwacker", 0], ["bushwacker", 0]]:  # mc2_01's lance (1.2)
		cbills += camp.price(p[0], p[1])
	for i in at:
		var fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % order[i]))
		for k in int(fit.get("Team0Objectives", {}).get("NumObjectives", 0)):
			var ob: Dictionary = fit.get("Team0Objective%d" % k, {})
			if int(ob.get("Priority", 0)) == 1:
				cbills += int(ob.get("ResourcePoints", 0))
		var pf := String(camp.mission_info(order[i]).get("PurchaseFile", ""))
		if pf != "" and not camp.bonus_files.has(pf):
			camp.bonus_files.append(pf)
		var bonus := "purbonus" + order[i].trim_prefix("mc2_")
		if FileAccess.file_exists("res://data/purchase/%s.json" % bonus):
			camp.bonus_files.append(bonus)
	var room := camp.drop_limit(mission)
	var options := camp.purchasable(mission)
	var lightest := INF
	for o in options:
		lightest = minf(lightest, float(o["tonnage"]))
	# A lance of heavies, as players field them: about one mech per 60 t of drop weight, the
	# weight spread evenly (each pick at most 15 t over an even share of what is left) so it
	# is not two assaults and a pair of 30 t scouts that die first.
	var count := clampi(roundi(room / 60.0), 1, Campaign.MAX_DEPLOY)
	var picked: Array[Dictionary] = []
	while picked.size() < count:
		var left := count - picked.size() - 1
		var best: Dictionary = {}
		for o in options:
			if float(o["tonnage"]) + left * lightest <= room + 0.01 and float(o["price"]) <= cbills \
					and float(o["tonnage"]) <= room / (left + 1) + 15.0 and (best.is_empty() \
					or o["tonnage"] > best["tonnage"] or (o["tonnage"] == best["tonnage"] and o["price"] > best["price"])):
				best = o
		if best.is_empty():
			break
		cbills -= float(best["price"])
		room -= float(best["tonnage"])
		picked.append(best)
	var free := camp.available_pilots(mission)
	free.sort_custom(func(a, b): return float(camp.pilots[a]["gunnery"]) + float(camp.pilots[a]["piloting"]) \
		> float(camp.pilots[b]["gunnery"]) + float(camp.pilots[b]["piloting"]))
	var force: Array = []
	for o in picked:
		if free.is_empty():
			break
		var p: String = free.pop_front()
		force.append({"chassis": o["chassis"], "variant": int(o["variant"]), "name": o["name"], "pilot": p,
			"gunnery": minf(Campaign.SKILL_CAP, float(camp.pilots[p]["gunnery"]) + 2.0 * at),
			"piloting": minf(Campaign.SKILL_CAP, float(camp.pilots[p]["piloting"]) + 1.0 * at)})
	return force


func _campaign_order() -> Array[String]:
	var c: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/campaign.json"))
	var order: Array[String] = []
	for g in int(c["Campaign"]["GroupCount"]):
		for mi in int(c.get("Group%d" % g, {}).get("MissionCount", 0)):
			var mis: Dictionary = c.get("Group%dMission%d" % [g, mi], {})
			if mis.has("FileName"):
				order.append(String(mis["FileName"]).to_lower())
	return order


func _force_text(sm: SimMission, force: Array) -> String:
	var names := []
	var tons := 0.0
	for u in sm.world.units:
		if u.team == sm.player_team and u.commander == 0 and u.is_mover() and u.on_gui and u.exists:
			names.append("%s(%s)" % [u.variant_name if u is SimMech and u.variant_name != "" else u.name, u.pilot_profile])
			tons += u.tonnage
	var limit := float(sm.fit.get("MissionSettings", {}).get("DropWeightLimit", Campaign.DEFAULT_DROP_LIMIT))
	return "%s %d units %.0f t of %.0f t, RP %d: %s" % ["campaign" if not force.is_empty() else "fit", names.size(), tons,
		limit, sm.support.rp if sm.support else 0, ", ".join(names)]


# --- play --------------------------------------------------------------------------------

func _lance(w: SimWorld) -> Array:
	return w.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover() \
		and u.exists and not u.is_disabled() and not u.hulk and u.on_gui and u.refit_pool <= 0.0 and u.num_weapons > 0)


func _centre(units: Array) -> Vector2:
	var c := Vector2.ZERO
	for m in units:
		c += m.position
	return c / maxf(units.size(), 1)


func _armed_enemy(u: SimUnit) -> bool:
	return u.team != 0 and u.is_mover() and u.exists and u.awake and not u.is_disabled() and not u.hulk and u.num_weapons > 0


## A methodical player: pull badly damaged mechs back, fight the armed enemies near the lance
## with focus fire, otherwise work the current objective as a group.
func _orders(sm: SimMission) -> void:
	var w := sm.world
	var lance := _lance(w)
	if lance.is_empty():
		return
	var centre := _centre(lance)
	for m in lance:  # don't chase a runner (e.g. a hovercraft over water) across the map
		if m.order == SimWorld.Order.ATTACK and m.order_target and m.distance_to(m.order_target.position) > ENGAGE_M * 1.5:
			_order(sm, m, "stop", null)
	var threats := w.units.filter(func(u): return _armed_enemy(u) \
		and lance.any(func(m): return m.distance_to(u.position) <= ENGAGE_M))
	_use_support(sm, lance, centre, threats)
	var task := _task(sm, lance, centre)
	if _trace:
		var key := "%s %s" % [task.get("kind", "-"), (task["target"] as SimUnit).name if task.has("target") else str(task.get("area", ""))]
		if threats.size() > 0:
			key = "fight %d threats" % threats.size()
		if key != _last_task:
			_last_task = key
			print("t=%6.1f  TASK %s  (lance %d at %.0f,%.0f)" % [w.time, key, lance.size(), centre.x, centre.y])
	var fighters := []
	for m in lance:
		if not _pull_back(sm, m, lance, centre, threats, task):
			fighters.append(m)
	if fighters.is_empty():
		return
	centre = _centre(fighters)
	if threats.is_empty():
		_safe = centre  # the last place the lance stood with nobody near
	else:
		if _fall_back(sm, fighters, centre, threats, task):
			return
		_fight(sm, fighters, threats)
		return
	if _repair_lull(sm, fighters, task):
		return
	match String(task.get("kind", "")):
		"attack":
			var t: SimUnit = task["target"]
			if t.distance_to(centre) > ENGAGE_M * 0.8 and _path_ok(sm, fighters[0], t):
				# close as a group to a point short of it, then everyone attacks
				for m in _group_move(sm, fighters, centre, t.position + (centre - t.position).normalized() * ENGAGE_M * 0.5, 25.0):
					if not (m.order == SimWorld.Order.ATTACK and m.order_target == t):
						_order(sm, m, "attack", t)  # no walk to the staging point: straight at it
			else:
				for m in fighters:
					if not (m.order == SimWorld.Order.ATTACK and m.order_target == t):
						_order(sm, m, "attack", t)
		"capture":
			_capture(sm, fighters, centre, task["target"])
		"move":
			_group_move(sm, fighters, centre, task["area"], minf(task["radius"] * 0.5, 25.0))
		"extract":
			_group_move(sm, lance, _centre(lance), task["area"], minf(task["radius"] * 0.5, 6.0 * sqrt(lance.size())))


## The current job: open primary objectives (hidden ones are unknown to the player), specific
## targets and markers before "destroy everything" and extraction last, in the designer's
## order; secondaries only when no primary needs anything.
func _task(sm: SimMission, lance: Array, centre: Vector2) -> Dictionary:
	var w := sm.world
	var objs := sm.objectives.objectives.filter(func(o): return not o["hidden"] and sm.objectives.is_active(o))
	var rank := func(o: Dictionary) -> int:
		var r := 0
		for c in o["conditions"]:
			if c["kind"] in ["DestroyAllEnemyUnits", "DestroyNumberOfEnemyUnits"]:
				r = maxi(r, 1)
			elif c["kind"] == "MoveAllSurvivingMechsToArea":
				r = maxi(r, 2)
		return (0 if o["primary"] else 10) + r
	objs.sort_custom(func(a, b): return rank.call(a) < rank.call(b) or (rank.call(a) == rank.call(b) and a["index"] < b["index"]))
	# Targets of opportunity, as a player shoots them on the way: unarmed enemy vehicles (fuel and
	# supply trucks) close to the lance, unless they can be captured (ordnance trucks pay RP) or sit
	# near something an objective wants captured (a fuel truck's blast took mc2_03's Mobile HQ).
	var keep := {}
	for o in sm.objectives.objectives:
		for c in o["conditions"]:
			if String(c["kind"]).begins_with("Capture") and c.get("unit") != null:
				keep[c["unit"]] = true
	var soft := w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists and u.awake and not u.is_disabled() \
		and not u.hulk and u.num_weapons == 0 and not keep.has(u) and u.position.distance_to(centre) <= 220.0 \
		and not (sm.abl and u.capturable and sm.abl.can_capture(u, 0)) \
		and not keep.keys().any(func(k): return not k.is_destroyed() and k.position.distance_to(u.position) < 120.0))
	if not soft.is_empty():
		soft.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
		return {"kind": "attack", "target": soft[0]}
	# Resource Points: a player takes the RP buildings and ordnance trucks near the route
	# (support-powers.md 1); support powers need them, and several missions start with 0 RP.
	if sm.abl:
		var rp_t := w.units.filter(func(u): return u.resource_points > 0 and u.capturable and sm.abl.can_capture(u, 0) \
			and u.position.distance_to(centre) <= 700.0 and _path_ok(sm, lance[0], u))
		if not rp_t.is_empty():
			rp_t.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
			return {"kind": "capture", "target": rp_t[0]}
	# In the designer's order (the numbered objectives follow the route; nearest-first sent
	# mc2_11's lance to objective 3 across the map first).
	for obj in objs:
		var job := _obj_task(sm, obj, lance, centre)
		if not job.is_empty():
			_cur_obj = int(obj["index"])
			return job
	return {}


var _cur_obj := -1  # the objective the bot is working
var _cur_target: SimUnit = null  # ... and its target
var _safe = null  # Vector2: the last place the lance stood with no threat near
var _fell_back := -INF
var _falling_until := -INF
var _lance_gone := false  # stopped by the harness: no armed lance unit left (I13)


## One objective's job: the nearest open target or marker of its conditions.
func _obj_task(sm: SimMission, obj: Dictionary, lance: Array, centre: Vector2) -> Dictionary:
	var w := sm.world
	var units := []
	for c in obj["conditions"]:
		if sm.objectives._cond_status(c, w) != SimObjectives.Status.UNDETERMINED:
			continue
		var kind: String = c["kind"]
		if kind in ["DestroyAllEnemyUnits", "DestroyNumberOfEnemyUnits"]:
			var all := w.units.filter(func(u): return u.team != 0 and u.is_mover() and u.exists \
				and not SimObjectives.dead(u) and not u.hulk and not _unreachable(sm, lance[0], u))
			var awake := all.filter(func(u): return u.awake)
			var pool := awake if not awake.is_empty() else all
			if pool.is_empty():
				continue
			pool.sort_custom(func(a, b): return _closer(sm, lance[0], centre, a, b))
			return {"kind": "attack", "target": pool[0]}
		elif kind == "MoveAllSurvivingMechsToArea":
			var near := _extract_blockers(w, c["center"]).filter(func(u): return u.team != 0 and not _unreachable(sm, lance[0], u))
			if not near.is_empty():
				near.sort_custom(func(a, b): return _closer(sm, lance[0], centre, a, b))
				return {"kind": "attack", "target": near[0]}
			return {"kind": "extract", "area": c["center"], "radius": float(c["radius"])}
		elif kind == "MoveAnyUnitToArea":
			return {"kind": "move", "area": c["center"], "radius": float(c["radius"])}
		elif c.get("unit") != null:
			var t: SimUnit = c["unit"]
			if t.is_disabled() or t.team == 0 or not t.exists:
				continue  # already ours (e.g. mc2_06 "protect" = capture own HQ), or not there yet
			units.append([t, kind])
	if units.is_empty():
		return {}
	units.sort_custom(func(a, b): return _closer(sm, lance[0], centre, a[0], b[0]))
	for u in units:  # finish the one already started
		if u[0] == _cur_target:
			units = [u]
			break
	var t: SimUnit = units[0][0]
	_cur_target = t
	if String(units[0][1]).begins_with("Capture") and sm.abl != null and sm.abl.can_capture(t, 0):
		return {"kind": "capture", "target": t}
	return {"kind": "attack", "target": t}


var _unreach := {}  # unit id -> time it was found unreachable (water, cliffs)
var _paths := {}  # unit id -> [time checked, a walking path to it exists]


## Is there a walking path from the lance to u (cached 30 s)? An attack order can still reach
## a target without one by firing from the nearest firing position.
func _path_ok(sm: SimMission, from: SimUnit, u: SimUnit) -> bool:
	var w := sm.world
	var c: Array = _paths.get(u.id, [-INF, false])
	if w.time - float(c[0]) > 30.0:
		c = [w.time, w.map.find_path(from.position, w.map.nearest_walkable(u.position, from.hover), from.hover).size() > 0]
		_paths[u.id] = c
	return c[1]


## Targets with a walking path first, then the nearest.
func _closer(sm: SimMission, from: SimUnit, centre: Vector2, a: SimUnit, b: SimUnit) -> bool:
	var pa := _path_ok(sm, from, a)
	if pa != _path_ok(sm, from, b):
		return pa
	return a.position.distance_to(centre) < b.position.distance_to(centre)


func _unreachable(sm: SimMission, from: SimUnit, u: SimUnit) -> bool:
	var w := sm.world
	if _unreach.has(u.id) and w.time - float(_unreach[u.id]) < 60.0:
		return true
	if u.hover and not from.hover and not w.map.is_walkable(w.map.cell_of(u.position), false):
		_unreach[u.id] = w.time  # a hovercraft on water: only reachable by fire
		return from.distance_to(u.position) > 200.0
	return false


## Units that keep MoveAllSurvivingMechsToArea open: any other commander's mover within 256 m
## of the point (SimObjectives quirk: allies too).
func _extract_blockers(w: SimWorld, area: Vector2) -> Array:
	return w.units.filter(func(u): return u.is_mover() and u.exists and u.commander != 0 and not SimObjectives.dead(u) \
		and not u.hulk and u.position.distance_to(area) <= SimObjectives.EXTRACT_CLEAR_M)


## Move as one group: each mech to its spot around the goal; a mech that has got well ahead
## of the lance centre waits for the rest (speeds differ: Werewolf 27 m/s, Zeus 19 m/s).
func _group_move(sm: SimMission, units: Array, centre: Vector2, goal: Vector2, spread: float) -> Array:
	var n := units.size()
	var dc := centre.distance_to(goal)
	var stuck := []
	for i in n:
		var m: SimUnit = units[i]
		var spot: Vector2 = sm.world.map.nearest_walkable(goal + (Vector2.from_angle(TAU * i / n) * spread if n > 1 else Vector2.ZERO), m.hover)
		if int(_stuck.get(m.id, 0)) >= 2:
			spot = sm.world.map.nearest_walkable(goal, m.hover)  # its spot can't be walked to: the goal itself
		var dm := m.distance_to(goal)
		if n > 1 and dm < dc - GROUP_M and m.distance_to(centre) > GROUP_M and dm > spread + 40.0:
			if m.order != SimWorld.Order.HOLD:
				_order(sm, m, "stop", null)
			_goal.erase(m.id)
			continue
		if m.distance_to(spot) <= 12.0:
			_stuck.erase(m.id)
			continue
		var last: Variant = _goal.get(m.id)
		if last != null and (last as Vector2).distance_to(spot) <= 20.0 and m.order == SimWorld.Order.HOLD:
			_stuck[m.id] = int(_stuck.get(m.id, 0)) + 1  # the move was refused or ended short
			if int(_stuck[m.id]) >= 4:
				stuck.append(m)
				continue
		if m.order == SimWorld.Order.HOLD or m.order == SimWorld.Order.ATTACK or last == null or (last as Vector2).distance_to(spot) > 20.0:
			_order(sm, m, "move", spot)
			_goal[m.id] = spot
	return stuck


## Focus fire: rank the threats by danger per point of health left (damaged and dangerous
## first, mechs over vehicles, near over far), then put the nearest guns on each in turn until
## they can strip it in about KILL_TIME; a mech already on a good target stays on it.
func _fight(sm: SimMission, fighters: Array, threats: Array) -> void:
	var score := {}
	for t in threats:
		var d := INF
		for m in fighters:
			d = minf(d, m.distance_to(t.position))
		var s := (_dps(t) + 0.5) / (_hp(t) + 30.0) * (1.5 if t is SimMech else 1.0)
		s /= 1.0 + maxf(0.0, d - 180.0) / 120.0
		score[t] = s
	var ranked := threats.duplicate()
	ranked.sort_custom(func(a, b): return score[a] > score[b])
	var want := {}
	var free := fighters.duplicate()
	for t in ranked:
		if free.is_empty():
			break
		var need := _hp(t) / KILL_TIME
		var have := 0.0
		free.sort_custom(func(a, b): return a.distance_to(t.position) < b.distance_to(t.position))
		while not free.is_empty() and have < need:
			var m: SimUnit = free.pop_front()
			want[m] = t
			have += _dps(m)
	for m in free:
		want[m] = ranked[0]
	var mid := _centre(fighters)
	for m in fighters:
		var t: SimUnit = want[m]
		# Leash: a mech that has chased off more than LEASH_M from the rest comes back unless its
		# target is already in its reach (pursuit into the next enemy group killed lone mechs, I18).
		if fighters.size() > 1 and m.distance_to(mid) > LEASH_M and m.distance_to(t.position) > sm.world.attack_range(m) / 0.9:
			if m.order != SimWorld.Order.MOVE or _goal.get(m.id) == null:
				_order(sm, m, "move", sm.world.map.nearest_walkable(mid, m.hover))
				_goal[m.id] = mid
			continue
		_goal.erase(m.id)
		var cur: SimUnit = m.order_target if m.order == SimWorld.Order.ATTACK else null
		if cur != null and score.has(cur) and score[cur] >= 0.7 * score[t]:
			continue
		if cur != t:
			_order(sm, m, "attack", t)


## Capture: clear the guards first (an armed enemy within 75 m of the target refuses it),
## then one mech captures while the rest guard it.
func _capture(sm: SimMission, units: Array, centre: Vector2, t: SimUnit) -> void:
	var w := sm.world
	var guards := w.units.filter(func(u): return u != t and u.team != 0 and u.is_mover() and u.exists and not u.is_disabled() \
		and not u.hulk and u.num_weapons > 0 and u.position.distance_to(t.position) <= SimAbl.BLOCK_CAPTURE_M + 10.0)
	if not guards.is_empty():
		guards.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
		for m in units:
			if not (m.order == SimWorld.Order.ATTACK and guards.has(m.order_target)):
				_order(sm, m, "attack", guards[0])
		return
	if t.distance_to(centre) > ENGAGE_M:
		_group_move(sm, units, centre, t.position, 30.0)
		return
	var capturer: SimUnit = null
	for m in units:
		if m is SimMech and m.brain is SimAbl.Pilot and int(m.brain.order.get("code", -1)) == SimAbl.TO_CAPTURE:
			capturer = m
	if capturer != null and capturer.order == SimWorld.Order.HOLD:
		# A capture order that left the mech standing short of the target (its walk goal could not
		# be reached): count it, re-issue it, then walk it straight at the target.
		_cap_stall[capturer.id] = int(_cap_stall.get(capturer.id, 0)) + 1
		var n := int(_cap_stall[capturer.id])
		if _trace:
			print("t=%6.1f  CAPTURE stalled x%d: %s at %.0f m from %s" % [sm.world.time, n, capturer.name, capturer.distance_to(t.position), t.name])
		if n % 3 == 0:
			_order(sm, capturer, "move", sm.world.map.nearest_walkable(t.position, capturer.hover))
		else:
			_order(sm, capturer, "capture", t)
	if capturer == null:
		var mechs := units.filter(func(m): return m is SimMech and m.brain is SimAbl.Pilot)
		mechs.sort_custom(func(a, b): return a.distance_to(t.position) < b.distance_to(t.position))
		if not mechs.is_empty():
			capturer = mechs[0]
			_order(sm, capturer, "capture", t)
			_goal.erase(capturer.id)
	var rest := units.filter(func(m): return m != capturer)
	_group_move(sm, rest, _centre(rest) if not rest.is_empty() else centre, t.position, 40.0)


## Pull a badly damaged mech out of the fight (to the repair truck if there is one, else behind
## the lance) while at least half the lance keeps fighting; back in once repaired or once the
## fight is over with no repair to be had. Extraction takes everyone. True if it is pulled back.
func _pull_back(sm: SimMission, m: SimUnit, lance: Array, centre: Vector2, threats: Array, task: Dictionary) -> bool:
	var w := sm.world
	var s: SimSupport = sm.support
	var trucks := w.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0 and not u.is_disabled() and u.exists)
	var can_repair := not trucks.is_empty() or (s != null and s.rp >= int(SimSupport.COSTS["repair_truck"])) \
		or (s != null and s.delivering)
	var h := _health(m)
	if _retreat.has(m.id):
		if h >= RESUME_FRAC or (threats.is_empty() and not can_repair) or String(task.get("kind", "")) == "extract" \
				or not (m is SimMech and SimSupport.needs_refit(m)):
			_retreat.erase(m.id)
			return false
	elif m is SimMech and h < RETREAT_FRAC and (can_repair or not threats.is_empty()) and String(task.get("kind", "")) != "extract":
		var out := lance.filter(func(o): return _retreat.has(o.id)).size()
		if (out + 1) * 2 > lance.size():
			return false
		_retreat[m.id] = true
		if _verbose:
			print("t=%6.1f  PULLBACK %s at %.0f%%" % [w.time, m.name, 100.0 * h])
	else:
		return false
	_goal.erase(m.id)
	if not trucks.is_empty():
		trucks.sort_custom(func(a, b): return a.distance_to(m.position) < b.distance_to(m.position))
		var truck: SimUnit = trucks[0]
		if s and not s.repairs.any(func(r): return r["mech"] == m):
			if not s.repairs.any(func(r): return r["truck"] == truck):
				s.order_repair(truck, m)
			elif m.distance_to(truck.position) > 60.0:
				_order(sm, m, "move", truck.position)
		return true
	var away := centre
	if not threats.is_empty():
		var tc := _centre(threats)
		away = centre + (centre - tc).normalized() * 150.0
	if m.distance_to(away) > 40.0 and (m.order != SimWorld.Order.MOVE or m.path.is_empty()):
		_order(sm, m, "move", w.map.nearest_walkable(away))
	return true


## Outgunned (the threats in reach out-shoot the lance by half again and it is worn), fall back
## towards the last quiet spot so the chasers arrive strung out, fast ones first, and fight
## there. Not during extraction (the area has to be cleared) and at most once per 60 s.
func _fall_back(sm: SimMission, units: Array, centre: Vector2, threats: Array, task: Dictionary) -> bool:
	var w := sm.world
	if String(task.get("kind", "")) == "extract" or _safe == null:
		return false
	if w.time < _falling_until:
		for m in units:
			if m.distance_to(_safe) > 40.0 and (m.order != SimWorld.Order.MOVE or m.path.is_empty()):
				_order(sm, m, "move", w.map.nearest_walkable(_safe, m.hover))
		return centre.distance_to(_safe) > 60.0
	if w.time - _fell_back < 60.0:
		return false
	var theirs := 0.0
	for t in threats:
		theirs += _dps(t)
	var ours := 0.0
	var health := 0.0
	for m in units:
		ours += _dps(m)
		health += _health(m)
	health /= maxf(units.size(), 1)
	if theirs < 1.5 * ours or health > 0.6 or centre.distance_to(_safe) < 150.0:
		return false
	_fell_back = w.time
	_falling_until = w.time + 25.0
	if _verbose:
		print("t=%6.1f  FALLBACK %d threats (dps %.0f vs %.0f, health %.0f%%) to (%.0f, %.0f)" % [w.time, threats.size(),
			theirs, ours, 100.0 * health, _safe.x, _safe.y])
	for m in units:
		_order(sm, m, "move", w.map.nearest_walkable(_safe, m.hover))
		_goal.erase(m.id)
	return true


## In a lull with a repair truck out, the lance gathers at the truck until it has patched up
## everyone under 70% (or run dry) before taking on the next job (I17, I19). Extraction waits
## for nothing.
func _repair_lull(sm: SimMission, units: Array, task: Dictionary) -> bool:
	var w := sm.world
	if String(task.get("kind", "")) == "extract":
		return false
	var trucks := w.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0 and not u.is_disabled() and u.exists)
	var waiting := sm.support != null and sm.support.delivering and sm.support.pending.any(func(p): return p["kind"] == "vtol")
	if trucks.is_empty() and not waiting:
		return false
	var hurt := units.filter(func(m): return m is SimMech and _health(m) < RESUME_FRAC and SimSupport.needs_refit(m))
	if hurt.is_empty():
		return false
	var at: Vector2 = trucks[0].position if not trucks.is_empty() else _centre(units)
	for m in units:
		if sm.support.repairs.any(func(r): return r["mech"] == m):
			continue
		if m.distance_to(at) > 50.0 and (m.order != SimWorld.Order.MOVE or m.path.is_empty()):
			_order(sm, m, "move", w.map.nearest_walkable(at, m.hover))
			_goal.erase(m.id)
	return true


## Orders go through the lance's pbrain, as the player's do (CommandInput). The bot keeps
## Run on (the original's Space held): a player order walks otherwise (I82).
func _order(sm: SimMission, m: SimUnit, kind: String, arg: Variant) -> void:
	if sm.abl and m.brain is SimAbl.Pilot:
		sm.abl.player_order(m, kind, arg, {"run": true})
	elif kind == "attack":
		sm.world.order_attack(m, arg)
	elif kind == "stop":
		sm.world.order_stop(m)
	else:
		sm.world.order_move(m, arg)


func _dps(u: SimUnit) -> float:
	var d := 0.0
	for i in u.weapon_indices():
		if u.items[i]["disabled"] or u.weapon_shots(i) == 0:
			continue
		var wpn := u.weapon(i)
		d += float(wpn.get("damage", 0.0)) / maxf(float(wpn.get("recycle", 1.0)), 0.5)
	return d


func _hp(u: SimUnit) -> float:
	var t := 0.0
	for a in u.armor:
		t += a
	if u is SimMech:
		for i in u.internal:
			t += i
	return t


func _health(m: SimUnit) -> float:
	var a := 0.0
	var b := 0.0
	for i in m.armor.size():
		a += m.armor[i]
		b += m.max_armor[i]
	if m is SimMech:
		for i in m.internal.size():
			a += m.internal[i]
			b += m.max_internal[i]
	return a / maxf(b, 1.0)


func _support(sm: SimMission, kind: String, target: Variant) -> bool:
	if not sm.support.call_power(kind, target):
		return false
	if _verbose:
		var where: String = (target as SimUnit).name if target is SimUnit else "(%.0f, %.0f)" % [target.x, target.y]
		print("t=%6.1f  SUPPORT %s %s rp_left=%d" % [sm.world.time, kind, where, sm.support.rp])
	return true


## Support powers the way a player uses them, most valuable first: the salvage craft on a
## disabled mech (ours first, then the heaviest enemy: a whole mech for 10000 RP), a repair
## truck set to work in a lull, an air strike on bunched enemies away from our units and from
## anything we must capture, a sensor probe ahead when RP is plentiful.
func _use_support(sm: SimMission, lance: Array, centre: Vector2, threats: Array) -> void:
	var s: SimSupport = sm.support
	var w := sm.world
	if s == null:
		return
	var trucks := w.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0 and not u.is_disabled() and u.exists)
	for t in trucks:  # idle trucks: the most damaged mech that is out of the fight
		if s.repairs.any(func(r): return r["truck"] == t):
			continue
		var worst: SimUnit = null
		for m in lance:
			if not (m is SimMech and SimSupport.needs_refit(m)) or s.repairs.any(func(r): return r["mech"] == m):
				continue
			if threats.any(func(e): return e.distance_to(m.position) < 200.0) and not _retreat.has(m.id):
				continue
			if worst == null or _health(m) < _health(worst):
				worst = m
		if worst and (_health(worst) < 0.9 or threats.is_empty()):
			s.order_repair(t, worst)
	if s.can_call("salvage_craft"):
		var cands := w.units.filter(func(u): return u is SimMech and u.is_disabled() and not u.is_destroyed() and u.exists \
			and u.position.distance_to(centre) <= 600.0)
		cands.sort_custom(func(a, b): return (a.team == 0 and b.team != 0) or (a.team == b.team and a.tonnage > b.tonnage))
		for u in cands:
			if _support(sm, "salvage_craft", u):
				return
	var hurt := lance.filter(func(m): return m is SimMech and _health(m) < (0.75 if threats.is_empty() else 0.6))
	var reserve := int(SimSupport.COSTS["repair_truck"]) if trucks.is_empty() else 0
	if s.can_call("repair_truck") and trucks.is_empty() and not hurt.is_empty() \
			and (threats.is_empty() or not _retreat.is_empty()):
		var at := centre
		if not threats.is_empty():
			at = centre + (centre - _centre(threats)).normalized() * 120.0
		if _support(sm, "repair_truck", w.map.nearest_walkable(at)):
			return
	var striking := s.pending.filter(func(p): return p["kind"] == "strike" and int(p.get("team", 0)) == sm.player_team)
	if s.can_call("air_strike") and s.rp - int(SimSupport.COSTS["air_strike"]) >= reserve and threats.size() >= 2 \
			and w.time - _last_strike >= 12.0:
		var keep := w.units.filter(func(u): return u.exists and not u.is_destroyed() and (u.team == 0 \
			or (u.capturable and sm.abl and sm.abl.can_capture(u, 0))))
		var best_at = null
		var best := 0.0
		for t in threats:
			var bunch := threats.filter(func(o): return o.position.distance_to(t.position) <= SimSupport.STRIKE_REACH_M)
			var value := 0.0
			for o in bunch:
				value += 2.0 if o is SimMech else 1.0
			if value < 2.5 or value <= best or striking.any(func(p): return (p["at"] as Vector2).distance_to(t.position) < 60.0):
				continue
			if keep.any(func(k): return k.position.distance_to(t.position) <= STRIKE_GUARD_M \
					+ ((k as SimStructure).extent_m if k is SimStructure else 0.0)):
				continue
			best = value
			best_at = t.position
		if best_at != null and _support(sm, "air_strike", best_at):
			_last_strike = w.time
			return
	if s.can_call("sensor_probe") and threats.is_empty() and s.probes.is_empty() \
			and w.time > 30.0 and s.rp >= int(SimSupport.COSTS["sensor_probe"]) + 2 * int(SimSupport.COSTS["repair_truck"]) + int(SimSupport.COSTS["air_strike"]):
		var task := _task(sm, lance, centre)
		var goal: Variant = task.get("area", (task["target"] as SimUnit).position if task.has("target") else null)
		if goal != null and centre.distance_to(goal) > 500.0:
			_support(sm, "sensor_probe", centre + (goal - centre).normalized() * 450.0)


func _play(sm: SimMission, max_t: float, args: PackedStringArray, verbose: bool) -> void:
	var w := sm.world
	var o := sm.objectives
	var next_order := 0.0
	_trace = "--trace" in args
	for a in args:
		if a.begins_with("--shots="):
			_shots_left = int(a.trim_prefix("--shots="))
	var gone_since := -1.0
	while w.time < max_t and o.result == SimObjectives.Result.PLAYING:
		sm.step()
		# Harness rule (I13): with no armed unit of the lance left, only support vehicles keep the
		# mission open (B6); a player has lost then. Stop and score it a loss after 30 s.
		if int(w.time * 10.0) % 10 == 0:
			if _lance(w).is_empty() and not w.units.any(func(u): return u.is_mover() and u.team == 0 and u.commander == 0 \
					and u.is_disabled() == false and u.on_gui and u.num_weapons > 0):
				if gone_since < 0.0:
					gone_since = w.time
				elif w.time - gone_since >= 30.0:
					_lance_gone = true
					if verbose:
						print("t=%6.1f  harness: no armed lance unit left since t=%.0f (only support vehicles); scored LOST (I13)" % [w.time, gone_since])
					break
			else:
				gone_since = -1.0
		for e in w.events:
			match e["type"]:
				"objective":
					if verbose and not e["hidden"]:
						print("t=%6.1f  objective done: %s" % [w.time, e["title"]])
				"disabled":
					var u: SimUnit = w.units[e["unit"]]
					if not verbose:
						continue
					if u.capturable and u.team != 0:
						print("t=%6.1f  capture target %s destroyed by %s" % [w.time, u.name, u.last_attacker.name if u.last_attacker else "?"])
					if u.team == 0:
						var arm := 0.0
						var top := 0.0
						for i in u.armor.size():
							arm += u.armor[i]
							top += u.max_armor[i]
						print("t=%6.1f  %sLOST %s (%s, armour %.0f%%, heat %.0f, ejected %s, pilot %s, last hit by %s)" % [w.time,
								"" if u.commander == 0 else "ALLY ", u.name,
							["normal", "shutdown", "disabled", "destroyed"][u.status], 100.0 * arm / maxf(top, 1.0), u.heat, u.ejected,
							u.pilot.status_text() if u.pilot and u.pilot.has_method("status_text") else (str(u.pilot.wounds) + " wounds" if u.pilot else "-"),
							u.last_attacker.name if u.last_attacker else "-"])
				"mission_end":
					if verbose: print("t=%6.1f  MISSION %s" % [w.time, "WON" if e["won"] else "LOST"])
				"impact":
					var victim: SimUnit = w.units[e["unit"]]
					if victim.team != 0 and int(e.get("from", -1)) >= 0 and w.units[e["from"]].commander == 0:
						_dealt += float(e.get("damage", 0.0))
					if victim.team == 0 and victim.commander == 0 and int(e.get("from", -1)) >= 0:
						var src: SimUnit = w.units[e["from"]]
						var key := "%s (%s)" % [src.name, "mech" if src is SimMech else "vehicle"]
						_damage[key] = _damage.get(key, 0.0) + float(e.get("damage", 0.0))
						_attackers[src.id] = true
						var loc := int(e.get("location", -1))
						_locs[loc] = _locs.get(loc, 0) + 1
				"shot":  # --shots=N: the first N shots, who fired at whom and under which brain (I12)
					if _shots_left > 0:
						_shots_left -= 1
						var a: SimUnit = w.units[e["from"]]
						var b: SimUnit = w.units[e["to"]]
						print("t=%6.1f  SHOT %s [team %d cmd %d %s%s] -> %s [team %d cmd %d %s]" % [w.time, a.name, a.team, a.commander,
							a.brain_name, " engaged" if a.brain_engaged else "", b.name, b.team, b.commander, b.brain_name])
				"abl_wave", "abl_video", "abl_music":
					if "--cues" in args:
						print("t=%6.1f  %s %s" % [w.time, e["type"], e.get("file", e.get("id", ""))])
		w.events.clear()
		if w.time >= next_order and not w.movie_mode:  # a player has no input during a cinematic
			next_order = w.time + 3.0
			_orders(sm)


# --- campaign mode ----------------------------------------------------------------------

## --campaign: play the campaign in order with persistent state (campaign-layer.md): equip
## each logistics mission from the inventory and the purchase list, apply wins, salvage,
## and retry a lost mission up to three times with new seeds.
func _campaign(data: Object, max_t: float) -> void:
	var camp := Campaign.create(data)
	var c: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/campaign.json"))
	var order: Array[String] = []
	for g in int(c["Campaign"]["GroupCount"]):
		for mi in int(c.get("Group%d" % g, {}).get("MissionCount", 0)):
			var mis: Dictionary = c.get("Group%dMission%d" % [g, mi], {})
			if mis.has("FileName"):
				order.append(String(mis["FileName"]).to_lower())
	for m in order:
		var won := false
		for attempt in 3:
			var force: Array = []
			if camp.plays_logistics(m) and not camp.mechs.is_empty():
				_equip(camp, m)
				force = camp.force()
			var sm := SimMission.load_mission(data, m, attempt + 1, true, force)
			_play(sm, max_t, PackedStringArray(), false)
			var r := MissionReport.from_sim(sm, m, data)
			won = r["won"]
			var names := []
			for f in force:
				names.append(String(f["chassis"]))
			print("%s try %d: %s at %.0f s | force %s (%d t of %d) | survivors %d | C-Bills %d" % [m, attempt + 1,
				"WON" if won else "lost", float(r["time"]), names if not names.is_empty() else "mission's own",
				int(camp.deployed_tonnage()), int(camp.drop_limit(m)), r["survivors"].size(), camp.c_bills])
			if won:
				camp.apply_win(r)
				_salvage(camp, r)
				break
		if not won:
			print("campaign stopped at %s; inventory %d 'Mechs, C-Bills %d" % [m, camp.mechs.size(), camp.c_bills])
			return
	print("CAMPAIGN COMPLETE; inventory %d 'Mechs" % camp.mechs.size())


## Fill the drop weight: owned 'Mechs heaviest first, then buy the heaviest affordable
## 'Mech that fits until nothing more fits; best pilots on the deployed 'Mechs.
func _equip(camp: Campaign, m: String) -> void:
	for mech in camp.mechs:
		camp.withdraw(mech)
	var owned := camp.mechs.duplicate()
	owned.sort_custom(func(a, b): return camp.tonnage(a["chassis"]) > camp.tonnage(b["chassis"]))
	for mech in owned:
		camp.deploy(mech, m)
	while camp.deployed().size() < Campaign.MAX_DEPLOY:
		var room := camp.drop_limit(m) - camp.deployed_tonnage()
		var best: Dictionary = {}
		for o in camp.purchasable(m):
			if o["tonnage"] <= room + 0.01 and o["price"] <= camp.c_bills and (best.is_empty() or o["tonnage"] > best["tonnage"]):
				best = o
		if best.is_empty():
			break
		camp.buy(String(best["chassis"]), int(best["variant"]))
		camp.deploy(camp.mechs[camp.mechs.size() - 1], m)
	var free := camp.available_pilots(m)
	free.sort_custom(func(a, b): return float(camp.pilots[a]["gunnery"]) + float(camp.pilots[a]["piloting"]) > float(camp.pilots[b]["gunnery"]) + float(camp.pilots[b]["piloting"]))
	for mech in camp.deployed():
		mech["pilot"] = free.pop_front() if not free.is_empty() else ""
	for mech in camp.deployed():
		if String(mech["pilot"]) == "":
			camp.withdraw(mech)


## Salvage the heaviest disabled 'Mechs the C-Bills allow.
func _salvage(camp: Campaign, r: Dictionary) -> void:
	var cands: Array = r.get("salvage", []).duplicate()
	cands.sort_custom(func(a, b): return camp.tonnage(a["chassis"]) > camp.tonnage(b["chassis"]))
	for s in cands:
		camp.buy_salvage(String(s["chassis"]), int(s["variant"]))
