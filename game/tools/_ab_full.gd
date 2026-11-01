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
	# A/B probes of the fidelity rules: --no-turrets, --no-remap, --rule=<SimRules field>=<value>
	SimMission.use_turrets = not ("--no-turrets" in args)
	SimMission.remap_building_teams = not ("--no-remap" in args)
	var sm := SimMission.load_mission(data, mission, seed_value, true, force)
	for a in args:
		if a.begins_with("--rule="):
			var kv := a.substr(7).split("=")
			var cur = sm.world.rules.get(kv[0])
			var val: Variant = (kv[1] == "true") if cur is bool else float(kv[1])
			sm.world.rules.set(kv[0], val)
			print("RULE %s = %s" % [kv[0], val])
	print("mission %s" % mission)
	print("force: %s" % _force_text(sm, force))
	print("ABL pilots: %d" % (sm.abl.pilots.size() if sm.abl else 0))
	var w := sm.world
	var o := sm.objectives
	for u in w.units:
		_start[u.id] = u.position
	_play(sm, max_t, args, true, mission)
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
				if c["kind"] in ["DestroyAllEnemyUnits", "DestroyNumberOfEnemyUnits"]:
					for u in w.units:
						if u.team != 0 and u.is_mover() and not SimObjectives.dead(u):
							print("      left: %s (team %d, brain %s, awake %s, exists %s, hulk %s, at %s, unreachable %s)" % [u.name,
								u.team, u.brain_name, u.awake, u.exists, u.hulk, u.position, _unreach.has(u.id)])
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
var _cap_trace := -INF  # --trace: last capture report
var _fight_trace := -INF  # --trace: last fight report
var _lull_trace := -INF  # --trace: last repair-lull report
var _side: SimUnit = null  # the capture on the way (RP building, turret control, bay) being worked
var _ignore := {}  # unit id -> until when the stall watch leaves it alone
var _stall_dealt := 0.0
var _stall_since := 0.0
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
## Missions the walkthroughs win by running to a base and holding it (docs/research/original-missions.md):
## the lance runs to the objective's area at once without stopping to fight, takes the turret
## controls and bays there, and fights only what comes inside `radius` until the area has been
## quiet for `quiet` seconds.
## - mc2_17: "As soon as the cutscene stops, RUN for that Steiner base to the east" [KC, BK];
##   capture its 2 turret controls and 2 repair bays and hold through the waves (Lee, 2026-10-24).
## "after": [objectives] delays a hold until they are decided; "at" names the point when no
## objective area does. Tried on mc2_18 (hold at its bay after the 3 recaptures, 2026-10-24): the
## waves' groups 3-4 only come once group 2 is dead (mc2_18.abl:368-391), and group 2 wrecks the
## city out of reach of a hold, so it stalled to 1800 s; not used.
## - mc2_22: "Stay in the corner and tease patrols into the turrets ... if you use the corner they
##   won't bother you" [KC]; "Lure the Catapults into the dell ... send one mech out as decoy" [CB].
##   The compound's guards attack only what comes within 300 m of their post (mc2_22_EC1_*.abl
##   setTargetPriority MOVER 300), so the lance holds the drop and a decoy brings them in, while
##   an air strike puts the northern turret line to sleep.
const HOLD_PLANS := {"mc2_17": {"objective": 2, "radius": 200.0, "quiet": 180.0},
	"mc2_22": {"at_start": true, "radius": 120.0, "quiet": 45.0, "watch": 450.0, "decoy": true},
	"mc2_23": {"after": [3], "at": Vector2(100.0, -350.0), "radius": 120.0, "quiet": 60.0, "watch": 500.0, "decoy": true,
		"lure_mechs": true, "lure_s": 45.0}}
## - mc2_23: "Tease the starport mechs out a few at a time" [KC, CB]: once the town is clear
##   (objective 3), the lance waits north-west of the starport and a decoy draws its guards out.
## Stealth missions: the walkthroughs avoid the patrols rather than fight them, and work some
## objectives out of the designer's order (docs/research/original-missions.md).
## - mc2_14 (solo Lao Hu): "take the airport first" (its turret controls, bay and the sensor
##   control, objective 6), then "watch the patrols on sensors and avoid ... them" [KC, CB]
##   (Lee, 2026-10-24: avoid patrols rather than fight them).
const STEALTH_PLANS := {"mc2_14": {"first": [6]}}
## Objectives the walkthroughs take first, out of the designer's order (docs/research/original-missions.md):
## - mc2_13: "Go to the dropship first and blow the fuel tanks on the Thor and Ryoken as they
##   charge", then its repair bay and sensor control [KC, CB, SOE, BK]; objective 4 is the dropship.
##   Weapons Facility #3 sits beside it, and #2 is the Powered Armor nest the guides keep for last
##   ("Don't fight the Powered Armor in the open" [CB, BK]).
##   "The Gauss Turret bases are incredibly deadly ... should be avoided at all costs" [SOE]:
##   "arcs" keeps the lance from chasing a target into an enemy fort's arcs (it fires from where
##   it stands instead). Not a default: on mc2_03 it cost 4/4 -> 0/4 (2026-10-24).
## - mc2_18: "Recapture HQ, power and sensor control" first (the secondaries "are worth a lot")
##   [KC, BK, CB]: objectives 2 (HQ, by the drop), 3 (power generator), 4 (sensor control).
##   "rp_reserve" keeps two repair trucks' worth of RP from strikes and salvage ("repair in the
##   lulls" [KC, CB]); the city's bay is lost mid-mission in most runs.
const ROUTE_PLANS := {"mc2_13": {"first": [4, 3, 1, 0, 2], "arcs": true},
	"mc2_18": {"first": [2, 3, 4], "arcs": true, "rp_reserve": 12000},
	"mc2_24": {"via": [Vector2(600.0, -1100.0), Vector2(1150.0, -400.0), Vector2(1250.0, 500.0), Vector2(1150.0, 900.0)],
		"first": [4], "run_out": true},
	"mc2_23": {"spare": 0, "prep_at": Vector2(620.0, -830.0), "prep_guns": 2, "rp_reserve": 24000,
		"mines": [[Vector2(200.0, -560.0), Vector2(200.0, -800.0)], [Vector2(200.0, -820.0), Vector2(200.0, -1060.0)]]}}
## "mines": segments a minelayer lays during the preparation, across the waves' approach and off
## the lance's own ground (mines have no team check, support-powers.md 3.5). mc2_23: KC spends the
## 36k on "several minelayers" around the western road and the starport's NW edge; the waves come
## in from the west edge.
## - mc2_24: "Do NOT assault the main gate" [KC]: "via" walks the lance east, out of the main
##   gate's turrets (Long Toms on both horns), round to the rebels who breach the east wall (team 2,
##   from (1300-1470, 985)), and in with them; objective 4 (the fuel trucks inside) starts their
##   mech attack (mc2_24.abl:281-289) [KC, BK, CB].
## - mc2_23: "The trick is to PREPARE a proper reception for the reinforcements BEFORE they
##   arrive" [KC]. The two reinforcement waves come 3 s after objective 0 (the starport force) is
##   done (mc2_23.abl:207-215), so "spare" leaves the last of its targets alive. Meanwhile the
##   lance takes the bays by the dropships, repairs, and puts Long Toms at "prep_at" ("3 artillery
##   pieces" [KC]; "4 Long Toms by each repair bay" [BK]), with RP kept back for them
##   ("rp_reserve"). Then it kills the last target and holds there.
const AVOID_M := 360.0  # stealth: an unengaged patrol this close is walked away from


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
	# not the support deliveries that can't fight alongside: trucks, the immobile artillery piece
	return w.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover() \
		and u.exists and not u.is_disabled() and not u.hulk and u.on_gui and u.refit_pool <= 0.0 and u.num_weapons > 0 \
		and u.run_speed > 0.0 and not (u is SimVehicle and (u.mine_stock > 0 or u.laying_mines)))


func _centre(units: Array) -> Vector2:
	var c := Vector2.ZERO
	for m in units:
		c += m.position
	return c / maxf(units.size(), 1)


func _armed_enemy(u: SimUnit) -> bool:
	return SimWorld.hostile(u.team, 0) and u.is_mover() and u.exists and u.awake and not u.is_disabled() and not u.hulk and u.num_weapons > 0


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
	var threats := w.units.filter(func(u): return _armed_enemy(u) and float(_ignore.get(u.id, -INF)) < w.time \
		and lance.any(func(m): return m.distance_to(u.position) <= ENGAGE_M))
	if _spare >= 0 and not _ready:
		var left := []
		for c in sm.objectives.objectives[_spare]["conditions"]:
			var u: SimUnit = c.get("unit")
			if u != null and u.exists and not SimObjectives.dead(u):
				left.append(u)
		_spared = left[0] if left.size() == 1 else null
		if left.size() == 1 and _verbose and w.time - _avoid_said >= 60.0:
			_avoid_said = w.time
			print("t=%6.1f  SPARE %s: the last target of objective %d, kept until the reception is ready" % [w.time, left[0].name, _spare])
	threats = threats.filter(func(u): return u != _spared)
	_stall_watch(sm, threats)
	_use_support(sm, lance, centre, threats)
	if _spared != null and threats.is_empty() and _prepare(sm, lance, centre):
		return
	if not _hold_pending.is_empty() and (_hold_pending["after"] as Array).all(func(i): return int(sm.objectives.objectives[i]["status"]) != 0):
		_hold_at = _hold_pending["at"]
		_hold_r = float(_hold_pending["radius"])
		_hold_q = float(_hold_pending["quiet"])
		_hold_pending = {}
		if _verbose:
			print("t=%6.1f  HOLD from now at (%.0f, %.0f)" % [w.time, _hold_at.x, _hold_at.y])
	if _hold_at != null:
		threats = threats.filter(func(u): return u.position.distance_to(_hold_at) <= _hold_r + 200.0)
		if not _hold_reached:
			if centre.distance_to(_hold_at) > _hold_r * 0.6:
				_run_to(sm, lance, _hold_at)
				return
			_hold_reached = true
			_hold_quiet = w.time
			if _verbose:
				print("t=%6.1f  HOLD reached (%.0f, %.0f)" % [w.time, _hold_at.x, _hold_at.y])
		var watch := _hold_watch
		var waiting := w.units.filter(func(u): return _armed_enemy(u) and u.awake and u.is_mover() \
			and u.position.distance_to(_hold_at) <= _hold_r + watch)
		if not threats.is_empty() or not waiting.is_empty():
			_hold_quiet = w.time
		elif w.time - _hold_quiet >= _hold_q:
			if _verbose:
				print("t=%6.1f  HOLD over: quiet for %.0f s" % [w.time, _hold_q])
			_hold_at = null
		if _hold_at != null and _hold_decoy and threats.is_empty() and not waiting.is_empty():
			# "Leave the team in place and send one mech out as decoy" [CB]: the fastest sound mech
			# walks to just inside the nearest guard's reach and comes back with it in tow
			var ok := lance.filter(func(m): return m is SimMech and _health(m) > 0.6)
			ok.sort_custom(func(a, b): return a.run_speed > b.run_speed)
			waiting.sort_custom(func(a, b): return a.position.distance_to(_hold_at) < b.position.distance_to(_hold_at))
			var d: SimUnit = ok[0] if not ok.is_empty() else null
			var lure: SimUnit = null
			var spot := Vector2.ZERO
			for e in waiting:  # the nearest guard that can be lured without walking into a fort's arcs
				# mechs only ("tease the starport mechs out" [KC]): the vehicles stay at their posts
				if d == null or (_lure_mechs and not (e is SimMech)) or float(_lure_tries.get(e.id, 0.0)) > _lure_s:
					continue
				var p: Vector2 = w.map.nearest_walkable(e.position + (_hold_at - e.position).normalized() * 260.0, d.hover)
				if _covering(w, p).is_empty():
					lure = e
					spot = p
					break
			if lure == null:
				# nothing left to lure out: the rest stay at their posts, so get on with the mission
				if _verbose:
					print("t=%6.1f  HOLD over: no guard left to lure out (%d waiting)" % [w.time, waiting.size()])
				_hold_at = null
			else:
				_lure_tries[lure.id] = float(_lure_tries.get(lure.id, 0.0)) + 3.0
				if d.distance_to(spot) > 25.0 \
						and (d.order != SimWorld.Order.MOVE or (_goal.get(d.id, Vector2.INF) as Vector2).distance_to(spot) > 30.0):
					_order(sm, d, "move", spot)
					_goal[d.id] = spot
					if _verbose and w.time - _avoid_said >= 20.0:
						_avoid_said = w.time
						print("t=%6.1f  DECOY %s toward %s at %.0f m" % [w.time, d.name, lure.name, lure.position.distance_to(_hold_at)])
				for m in lance:
					if m != d and m.distance_to(_hold_at) > 40.0 and (m.order != SimWorld.Order.MOVE or m.path.is_empty()):
						_order(sm, m, "move", w.map.nearest_walkable(_hold_at, m.hover))
				return
	if _stealth:
		# A patrol that hasn't turned on us is avoided; only what is shooting at us (or guards
		# what we must take) is fought.
		var engaged := threats.filter(func(u): return lance.has(u.order_target) or float(u.last_attacked_time) > w.time - 15.0 \
			and u.last_attacker != null and lance.has(u.last_attacker))
		# a unit standing at its post (a fort's guards) is not a patrol to walk away from: avoiding
		# it for good stalled mc2_14 short of Gun Beta for 15 minutes
		for u in threats:
			if u.speed > 0.5:
				_moved[u.id] = w.time
		var near := threats.filter(func(u): return not engaged.has(u) and w.time - float(_moved.get(u.id, -INF)) < 30.0 \
			and lance.any(func(m): return m.distance_to(u.position) <= AVOID_M))
		# "avoid or ambush them one at a time" [KC]: a group we out-gun that is alone, or that has
		# sat across our way for a minute, is ambushed instead
		if not near.is_empty():
			var theirs_n := 0.0
			for u in near:
				theirs_n += _dps(u)
				_avoided[u.id] = float(_avoided.get(u.id, 0.0)) + 3.0
			var ours_n := 0.0
			for m in lance:
				ours_n += _dps(m)
			if theirs_n < 0.6 * ours_n and (near.size() == 1 or near.any(func(u): return float(_avoided[u.id]) >= 60.0)) \
					and _covering(w, centre).is_empty() and not near.any(func(u): return not _covering(w, u.position).is_empty()):
				engaged.append_array(near)
				near = []
		if threats.is_empty() and _covering(w, centre).is_empty():
			_quiet_spot = centre
		if engaged.is_empty() and not near.is_empty():
			var away := (centre - _centre(near)).normalized()
			var nc := _centre(near)
			if _quiet_spot != null and (_quiet_spot as Vector2).distance_to(nc) > centre.distance_to(nc) + 50.0 \
					and (_quiet_spot as Vector2).distance_to(centre) > 40.0:
				away = ((_quiet_spot as Vector2) - centre).normalized()  # back the way we came, where it was quiet
			var spot: Vector2 = w.map.nearest_walkable(centre + away * 200.0)
			for turn in [0.0, 45.0, -45.0, 90.0, -90.0]:  # not into an enemy fort's arcs
				var p2: Vector2 = w.map.nearest_walkable(centre + away.rotated(deg_to_rad(turn)) * 200.0)
				if _covering(w, p2).is_empty():
					spot = p2
					break
			if _verbose and w.time - _avoid_said >= 20.0:
				_avoid_said = w.time
				print("t=%6.1f  AVOID %d patrol units (nearest %s at %.0f m, avoided %.0f s, speed %.1f, in arcs %s/%s)" % [w.time,
					near.size(), near[0].name, near[0].distance_to(centre), float(_avoided.get(near[0].id, 0.0)), near[0].speed,
					not _covering(w, centre).is_empty(), near.any(func(u): return not _covering(w, u.position).is_empty())])
			for m in lance:
				if m.order != SimWorld.Order.MOVE or m.path.is_empty() or (_goal.get(m.id, Vector2.INF) as Vector2).distance_to(spot) > 60.0:
					_order(sm, m, "move", spot)
					_goal[m.id] = spot
			return
		threats = engaged
		# Outgunned or worn: lure them back into our captured turrets, or to a bay ("Retreat to
		# forts. Hop between bays" [KC, CB]).
		if not engaged.is_empty():
			var theirs := 0.0
			for u in engaged:
				theirs += _dps(u)
			var ours := 0.0
			var hp := 0.0
			for m in lance:
				ours += _dps(m)
				hp += _health(m)
			hp /= lance.size()
			var bay: SimStructure = _bay_for(sm, lance[0]) if lance.size() == 1 else null
			if hp < 0.45 and bay != null and _to_bay(sm, lance[0]):
				return  # hop to a bay
			if theirs > 0.8 * ours or hp < 0.5:
				var forts := w.units.filter(func(u): return u is SimTurret and u.team == 0 and u.active and not u.is_destroyed() \
					and u.num_weapons > 0 and u.position.distance_to(centre) <= 700.0)
				forts.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
				var fort_dps := 0.0
				for f in forts:
					if f.position.distance_to(forts[0].position) <= 120.0:
						fort_dps += _dps(f)
				if (forts.is_empty() or fort_dps + ours < theirs) and _quiet_spot != null \
						and (_quiet_spot as Vector2).distance_to(centre) > 150.0:
					# no fort of ours strong enough to turn it: break contact back the way we came
					var q: Vector2 = _quiet_spot
					if _verbose and w.time - _avoid_said >= 20.0:
						_avoid_said = w.time
						print("t=%6.1f  BREAK %d attackers to (%.0f, %.0f) (dps %.0f vs %.0f + forts %.0f, health %.0f%%)" % [w.time,
							engaged.size(), q.x, q.y, theirs, ours, fort_dps, 100.0 * hp])
					for m in lance:
						if m.order != SimWorld.Order.MOVE or m.path.is_empty() or (_goal.get(m.id, Vector2.INF) as Vector2).distance_to(q) > 40.0:
							_order(sm, m, "move", w.map.nearest_walkable(q, m.hover))
							_goal[m.id] = q
					return
				if not forts.is_empty():
					var fc := _centre(forts)
					var near_fort: Vector2 = forts[0].position
					if centre.distance_to(near_fort) > 70.0:
						var spot2: Vector2 = w.map.nearest_walkable(near_fort + (fc - near_fort).normalized() * 30.0)
						if _verbose and w.time - _avoid_said >= 20.0:
							_avoid_said = w.time
							print("t=%6.1f  LURE %d to our turrets at (%.0f, %.0f) (dps %.0f vs %.0f, health %.0f%%)" % [w.time,
								engaged.size(), spot2.x, spot2.y, theirs, ours, 100.0 * hp])
						for m in lance:
							if m.order != SimWorld.Order.MOVE or m.path.is_empty() or (_goal.get(m.id, Vector2.INF) as Vector2).distance_to(spot2) > 40.0:
								_order(sm, m, "move", spot2)
								_goal[m.id] = spot2
						return
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
	if _run_out and String(task.get("kind", "")) == "extract":
		# "RUN ... for extraction ... As long as ONE mech reaches the extraction, you win!" [KC]:
		# every survivor runs for it, nobody stops to fight (ROUTE_PLANS "run_out")
		_run_to(sm, lance, task["area"])
		return
	if threats.is_empty():
		_safe = centre  # the last place the lance stood with nobody near
	else:
		if _hold_at == null and _fall_back(sm, fighters, centre, threats, task):
			return
		_fight(sm, fighters, threats)
		return
	if _repair_lull(sm, fighters, task):
		return
	if _hold_at != null:
		# holding: nothing outside the base is worth leaving it for; wait inside it
		var tu: SimUnit = task.get("target")
		if (tu == null and String(task.get("kind", "")) != "capture") or (tu != null and tu.position.distance_to(_hold_at) > _hold_r + 150.0):
			_group_move(sm, fighters, centre, _hold_at, 40.0)
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
		return (-100 + 10 * _first.find(int(o["index"])) if _first.has(int(o["index"])) else 0 if o["primary"] else 10) + r
	objs.sort_custom(func(a, b): return rank.call(a) < rank.call(b) or (rank.call(a) == rank.call(b) and a["index"] < b["index"]))
	if _run_out:
		# the extraction is open and it's the last primary: nothing on the way is worth a detour
		var open_p := objs.filter(func(o): return o["primary"])
		if open_p.size() == 1 and open_p[0]["conditions"].any(func(c): return c["kind"] == "MoveAllSurvivingMechsToArea"):
			var job := _obj_task(sm, open_p[0], lance, centre)
			if not job.is_empty():
				return job
	# Targets of opportunity, as a player shoots them on the way: unarmed enemy vehicles (fuel and
	# supply trucks) close to the lance, unless they can be captured (ordnance trucks pay RP) or sit
	# near something an objective wants captured (a fuel truck's blast took mc2_03's Mobile HQ).
	var keep := {}
	for o in sm.objectives.objectives:
		for c in o["conditions"]:
			if String(c["kind"]).begins_with("Capture") and c.get("unit") != null:
				keep[c["unit"]] = true
	var soft := w.units.filter(func(u): return SimWorld.hostile(u.team, 0) and u.is_mover() and u.exists and u.awake and not u.is_disabled() \
		and not u.hulk and u.num_weapons == 0 and not keep.has(u) and u.position.distance_to(centre) <= 220.0 \
		and not (sm.abl and u.capturable and sm.abl.can_capture(u, 0)) \
		and not keep.keys().any(func(k): return not k.is_destroyed() and k.position.distance_to(u.position) < 120.0))
	if not soft.is_empty():
		soft.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
		return {"kind": "attack", "target": soft[0]}
	# Enemy turret forts on the way (I99): the walkthroughs take out the control or generator
	# instead of the turrets, capturing a control where they can (docs/research/original-missions.md).
	if sm.abl:
		var fort := _fort_job(sm, lance, centre)
		if not fort.is_empty():
			return fort
	# Resource Points: a player takes the RP buildings and ordnance trucks near the route
	# (support-powers.md 1); support powers need them, and several missions start with 0 RP.
	# Turret controls and repair bays near the route too: every walkthrough fights inside captured
	# turrets and repairs at captured bays (docs/research/original-missions.md, I94, I95).
	if sm.abl:
		var rp_t := w.units.filter(func(u): return u.capturable and sm.abl.can_capture(u, 0) \
			and (u.resource_points > 0 or (u is SimStructure and (u.control or (u.can_refit and u.mech_bay) \
				or u.name.contains("SensorControl")))) \
			and u.position.distance_to(centre) <= (700.0 if u.resource_points > 0 else 450.0) and _path_ok(sm, lance[0], u))
		# keep the one already started (a group walk is slow; without this the lance swayed
		# between it and the next objective at the edge of the radius)
		if _side and is_instance_valid(_side) and not rp_t.has(_side) and sm.abl.can_capture(_side, 0) \
				and _side.position.distance_to(centre) <= 750.0:
			rp_t.append(_side)
		if not rp_t.is_empty():
			rp_t.sort_custom(func(a, b): return a == _side or (b != _side and a.position.distance_to(centre) < b.position.distance_to(centre)))
			_side = rp_t[0]
			return {"kind": "capture", "target": rp_t[0]}
		_side = null
	# A route round a defended front first (ROUTE_PLANS "via")
	while not _via.is_empty() and centre.distance_to(_via[0]) <= 120.0:
		_via.pop_front()
	if not _via.is_empty():
		return {"kind": "move", "area": _via[0], "radius": 60.0}
	# "follow the rebels in through the east breach" [KC, BK, CB]: behind the neutral team's armed
	# movers while they lead (ROUTE_PLANS "follow"), up to 6 minutes
	if _follow >= 0 and w.time - _follow_since < 360.0:
		var lead := w.units.filter(func(u): return u.team == _follow and u.is_mover() and u.exists and not u.is_disabled() \
			and u.num_weapons > 0)
		if lead.size() >= 2:
			if _follow_since < 0.0:
				_follow_since = w.time
			var lc := _centre(lead)
			var behind: Vector2 = lc + (centre - lc).normalized() * 120.0
			return {"kind": "move", "area": w.map.nearest_walkable(behind), "radius": 60.0}
	# In the designer's order (the numbered objectives follow the route; nearest-first sent
	# mc2_11's lance to objective 3 across the map first).
	for obj in objs:
		var job := _obj_task(sm, obj, lance, centre)
		if not job.is_empty():
			_cur_obj = int(obj["index"])
			if sm.abl and _unlocks:
				return _unlock(sm, job, lance)
			return job
	return {}


## An objective under an enemy fort's guns: first switch the fort off at its root, the control's
## generator if it has one (a destroyed parent puts its children to sleep, bldng.cpp:903-913,
## turret.cpp:620-633), else capture or destroy the control. mc2_13: "Kill the two generators in
## the NE crater to drop the HPG turrets" [KC, CB].
func _unlock(sm: SimMission, job: Dictionary, lance: Array) -> Dictionary:
	var w := sm.world
	var t: SimUnit = job.get("target")
	var at: Vector2 = t.position if t != null else job.get("area", Vector2.INF)
	if at == Vector2.INF:
		return job
	var best: SimStructure = null
	for tur in _covering(w, at):
		var ctl: SimStructure = tur.parent
		if ctl == null or ctl.is_destroyed() or ctl == t:
			continue
		var root: SimStructure = ctl
		if ctl.parent != null and not ctl.parent.is_destroyed() and ctl.parent.team != 0:
			root = ctl.parent
		if root.team == 0 or not _path_ok(sm, lance[0], root):
			continue
		if best == null or _covering(w, root.position).size() < _covering(w, best.position).size():
			best = root
	if best == null or _covering(w, best.position).size() >= _covering(w, at).size():
		return job
	if best.capturable and sm.abl.can_capture(best, 0) and best.parent == null:
		return {"kind": "capture", "target": best}
	return {"kind": "attack", "target": best}


var _stealth := false  # a STEALTH_PLANS mission: patrols are avoided
var _first: Array = []  # ... and these objectives are worked first
var _avoid_said := -INF
var _quiet_spot = null  # Vector2: the last place the stealth bot stood with no enemy in sight or fort arc
var _run_out := false  # ROUTE_PLANS "run_out": the extraction is a run, not a fight
var _follow := -1  # ROUTE_PLANS "follow": a neutral team the lance walks in behind
var _follow_since := -1.0
var _via: Array = []  # ROUTE_PLANS "via": points walked through before the objectives
var _spare := -1  # ROUTE_PLANS "spare": the objective whose last target is left alive until ready
var _spared: SimUnit = null
var _prep_at = null
var _prep_guns := 0
var _mine_segs: Array = []  # ROUTE_PLANS "mines": segments still to lay
var _mines_called := false
var _mine_at_start := false
var _rp_reserve := 0
var _prepping := false
var _ready := false
var _fort_strike := true  # --no-fort-strike: no air strike on a fort's generator (A/B)
var _unlocks := true  # --no-unlock: objectives under a fort aren't preceded by its generator (A/B)
var _bombs := true  # --no-bombs: no shooting explosive buildings under enemies (A/B)
var _arcs := false  # ROUTE_PLANS "arcs": no chasing into enemy forts' arcs
var _held := {}  # unit id -> its attack order fires from where it stands
var _moved := {}  # unit id -> last time the stealth bot saw it moving
var _avoided := {}  # unit id -> seconds the stealth bot has spent walking away from it
var _hold_at = null  # Vector2: the base a HOLD_PLANS mission holds, until it has been quiet
var _hold_r := 0.0
var _hold_q := 0.0
var _hold_reached := false
var _hold_pending := {}
var _hold_watch := 700.0  # enemies awake this far beyond the hold radius keep it going
var _lure_tries := {}  # enemy id -> seconds a decoy has spent trying to draw it out
var _hold_decoy := false
var _lure_mechs := false  # HOLD_PLANS "lure_mechs": the decoy draws out mechs only
var _lure_s := 90.0  # HOLD_PLANS "lure_s": seconds spent on each guard before giving up  # HOLD_PLANS "decoy": one mech lures the waiting guards to the hold  # a HOLD_PLANS entry waiting on its "after" objectives
var _hold_quiet := 0.0


## The reception before the last spared target dies: the lance gathers at "prep_at", repairs
## (bays, trucks), Long Toms go down there, then the target is released and the lance holds the
## spot for the waves. True while preparing (this tick's orders are given).
func _prepare(sm: SimMission, lance: Array, centre: Vector2) -> bool:
	var w := sm.world
	var at: Vector2 = _prep_at if _prep_at != null else centre
	if centre.distance_to(at) > 120.0:
		_group_move(sm, lance, centre, at, 30.0)
		return true
	var s: SimSupport = sm.support
	var guns := w.units.filter(func(u): return u.team == 0 and u.model == "artillerypiece" and u.exists and not u.is_disabled())
	if s != null and guns.size() < _prep_guns and s.can_call("artillery_piece") and not s.delivering:
		_prepping = true
		var k := guns.size()
		# behind the lance from the waves (they come from the west edge), out of its own blasts'
		# way (a Long Tom 60 m off had shelled our Catapult)
		var spot: Vector2 = w.map.nearest_walkable(at + Vector2(130.0, -50.0 + 50.0 * k))
		_support(sm, "artillery_piece", spot)
		_prepping = false
		return true
	if s != null and not _mine_segs.is_empty():
		var layers := w.units.filter(func(u): return u.team == 0 and u is SimVehicle and u.exists and not u.is_disabled() \
			and (u.mine_stock > 0 or u.laying_mines))
		if layers.is_empty():
			if s.delivering:
				return true
			if _mines_called or not s.can_call("minelayer"):
				_mine_segs.clear()  # it was lost or there's no RP: go without
			else:
				_prepping = true
				_mines_called = _support(sm, "minelayer", w.map.nearest_walkable(_mine_segs[0][0]))
				_prepping = false
				if not _mines_called:
					_mine_segs.clear()
			return true
		var ml: SimVehicle = layers[0]
		if ml.order == SimWorld.Order.MOVE:
			return true  # driving to a segment or laying one
		var seg: Array = _mine_segs[0]
		var a: Vector2 = w.map.nearest_walkable(seg[0])
		if ml.distance_to(a) > 20.0 and not _mine_at_start:
			w.order_move(ml, a, true)
			_mine_at_start = true
			return true
		if ml.mine_stock > 0:
			s.order_lay_mines(ml, w.map.nearest_walkable(seg[1]))
			if _verbose:
				print("t=%6.1f  MINES %s lays (%.0f, %.0f) -> (%.0f, %.0f), %d left" % [w.time, ml.name, a.x, a.y, seg[1].x, seg[1].y, ml.mine_stock])
		_mine_segs.pop_front()
		_mine_at_start = false
		if ml.mine_stock <= 0:
			_mine_segs.clear()
		return true
	var hurt := lance.filter(func(m): return m is SimMech and _health(m) < 0.85 and SimSupport.needs_refit(m) \
		and (_bay_for(sm, m) != null or not _trucks(sm).is_empty() or (s != null and s.rp >= int(SimSupport.COSTS["repair_truck"]))))
	if not hurt.is_empty() or (s != null and s.delivering):
		_repair_lull(sm, lance, {})
		for m in hurt:
			_to_bay(sm, m)
		return true
	_ready = true
	if _verbose:
		print("t=%6.1f  READY: %d guns at (%.0f, %.0f), lance repaired; releasing %s" % [w.time, guns.size(), at.x, at.y, _spared.name])
	_hold_at = at
	_hold_r = 220.0
	_hold_q = 150.0
	_hold_reached = true
	_hold_quiet = w.time
	_hold_watch = 900.0
	_spared = null
	return false


## Every mech runs straight to its own spot around the point, no waiting for the slow ones (a
## chase: a mech that stops for the rest is caught).
func _run_to(sm: SimMission, units: Array, at: Vector2) -> void:
	var n := units.size()
	for i in n:
		var m: SimUnit = units[i]
		var spot: Vector2 = sm.world.map.nearest_walkable(at + Vector2.from_angle(TAU * i / n) * 30.0, m.hover)
		var last: Variant = _goal.get(m.id)
		if m.order != SimWorld.Order.MOVE or m.path.is_empty() or last == null or (last as Vector2).distance_to(spot) > 20.0:
			_order(sm, m, "move", spot)
			_goal[m.id] = spot


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
			if t == _spared or t.is_disabled() or t.team == 0 or not t.exists:
				continue  # already ours (e.g. mc2_06 "protect" = capture own HQ), or not there yet
			units.append([t, kind])
	if units.is_empty():
		return {}
	units.sort_custom(func(a, b): return _closer(sm, lance[0], centre, a[0], b[0]))
	if int(obj["index"]) == _spare and not _ready and units.size() > 1:
		# leave the weakest for last: it is the one to spare ("leave one LRM carrier alive" [KC, CB])
		var weakest: Array = units[0]
		for u in units:
			if _dps(u[0]) + _hp(u[0]) / 50.0 < _dps(weakest[0]) + _hp(weakest[0]) / 50.0:
				weakest = u
		units.erase(weakest)
		units.append(weakest)
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
		if t is SimVehicle and t.model == "aerospotter":
			s *= 4.0  # it calls a large strike every 10 s on whoever it targets (I114); kill it first
		if not _covering(sm.world, t.position).is_empty():
			s *= 0.25  # under an enemy fort's guns: let it come out (I99; holding the lance out of the
			# arcs as well cost mc2_03 4/4 -> 0/4 in an A/B, 2026-10-24: it dithered on the edge)
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
	# Blow a fuel tank, pipe or ammo dump under the enemy (bldng.cpp:1476-1488): an enemy mech
	# inside a blast that reaches none of ours is worth the nearest gun's volley ("blow the fuel
	# tanks on the Thor and Ryoken as they charge", mc2_13; "use its fuel tanks on the pursuers",
	# mc2_17; ammo dumps on the Hunchbacks, mc2_14).
	var bomb := _bomb_for(sm, fighters, threats) if _bombs else null
	if bomb != null:
		fighters.sort_custom(func(a, b): return a.distance_to(bomb.position) < b.distance_to(bomb.position))
		want[fighters[0]] = bomb
		if fighters.size() > 3:
			want[fighters[1]] = bomb
	var mid := _centre(fighters)
	if _trace and sm.world.time - _fight_trace >= 30.0:
		_fight_trace = sm.world.time
		for m in fighters:
			var ot: SimUnit = m.order_target
			print("t=%6.1f  FIGHT %s order %d target %s d %.0f los %s path %d at (%.0f,%.0f) spd %.1f" % [sm.world.time, m.name, m.order,
				ot.name if ot else "-", m.distance_to(ot.position) if ot else -1.0, sm.world.line_of_sight(m, ot) if ot else false,
				m.path.size(), m.position.x, m.position.y, m.speed])
	for m in fighters:
		var t: SimUnit = want[m]
		# Leash: a mech that has chased off more than LEASH_M from the rest comes back unless its
		# target is already in its reach (pursuit into the next enemy group killed lone mechs, I18).
		var anchor: Vector2 = mid if _hold_at == null else _hold_at
		var leash := LEASH_M if _hold_at == null else _hold_r
		if (fighters.size() > 1 or _hold_at != null) and m.distance_to(anchor) > leash \
				and m.distance_to(t.position) > sm.world.attack_range(m) / 0.9:
			if m.order != SimWorld.Order.MOVE or _goal.get(m.id) == null:
				_order(sm, m, "move", sm.world.map.nearest_walkable(anchor, m.hover))
				_goal[m.id] = anchor
			continue
		_goal.erase(m.id)
		var cur: SimUnit = m.order_target if m.order == SimWorld.Order.ATTACK else null
		if t == bomb:
			if cur != t:
				_order(sm, m, "attack", t, {"force": true})  # a neutral building needs force fire
				if _verbose:
					print("t=%6.1f  BOMB %s shoots %s under %s" % [sm.world.time, m.name, t.name,
						threats.filter(func(e): return e is SimMech and e.distance_to(t.position) <= bomb.explosion_radius_m * 0.8).map(func(e): return e.name)])
			continue
		# (only while it can reach the target from where it stands: holding short of range stalled
		# mc2_18 on a capture guard for 15 minutes)
		var hold: bool = _arcs and _covering(sm.world, m.position).is_empty() and not _covering(sm.world, t.position).is_empty() \
			and m.distance_to(t.position) <= sm.world.attack_range(m)
		if cur != null and score.has(cur) and score[cur] >= 0.7 * score[t] and bool(_held.get(m.id, false)) == hold:
			continue
		if cur != t or bool(_held.get(m.id, false)) != hold:
			_order(sm, m, "attack", t, {"pursue": not hold})
			_held[m.id] = hold


## An intact enemy-side or neutral building that explodes, with an enemy mech in its blast and
## none of our units in it, within reach of one of the fighters.
func _bomb_for(sm: SimMission, fighters: Array, threats: Array) -> SimStructure:
	var w := sm.world
	var ours := w.units.filter(func(u): return u.team == 0 and u.is_mover() and u.exists and not u.is_disabled())
	var best: SimStructure = null
	var best_n := 0
	for u in w.units:
		if not (u is SimStructure) or u is SimTurret or u.is_destroyed() or u.explosion_damage < 20.0 or u.team == 0:
			continue
		var r: float = u.explosion_radius_m
		if not fighters.any(func(m): return m.distance_to(u.position) <= w.attack_range(m)):
			continue
		if ours.any(func(m): return m.distance_to(u.position) <= r + 10.0):
			continue
		if w.units.any(func(b): return b is SimStructure and b.team == 0 and not b.is_destroyed() \
				and b.position.distance_to(u.position) <= r + b.extent_m):
			continue  # our own bay or control in the blast (mc2_17: an ammo dump took our repair bay)
		var n := threats.filter(func(t): return t is SimMech and t.distance_to(u.position) <= r * 0.8).size()
		if n > best_n:
			best = u
			best_n = n
	return best


## Capture: clear the guards first (an armed enemy within 75 m of the target refuses it),
## then one mech captures while the rest guard it.
func _capture(sm: SimMission, units: Array, centre: Vector2, t: SimUnit) -> void:
	var w := sm.world
	if _trace and w.time - _cap_trace >= 30.0:
		_cap_trace = w.time
		var cp := units.filter(func(m): return m.brain is SimAbl.Pilot and int(m.brain.order.get("code", -1)) == SimAbl.TO_CAPTURE)
		print("t=%6.1f  CAPTURE %s at %.0f m from the lance; capturer %s order %d dist %.0f; can_capture %s" % [w.time, t.name,
			t.distance_to(centre), cp[0].name if cp else "-", cp[0].order if cp else -1, cp[0].distance_to(t.position) if cp else -1.0,
			sm.abl.can_capture(t, 0)])
	var guards := w.units.filter(func(u): return u != t and u.team != 0 and u.is_mover() and u.exists and not u.is_disabled() \
		and not u.hulk and u.num_weapons > 0 and u.position.distance_to(t.position) <= SimAbl.BLOCK_CAPTURE_M + 10.0)
	if not guards.is_empty():
		guards.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
		if _trace and w.time - _cap_trace >= 30.0:
			_cap_trace = w.time
			print("t=%6.1f  CAPTURE guards %d: %s (%s) at %.0f m, awake %s, contact %s" % [w.time, guards.size(), guards[0].name,
				guards[0].brain_name, guards[0].distance_to(centre), guards[0].awake, sm.abl.is_contact(0, guards[0])])
		for m in units:
			if not (m.order == SimWorld.Order.ATTACK and guards.has(m.order_target)):
				_order(sm, m, "attack", guards[0])
		return
	if t.distance_to(centre) > ENGAGE_M:
		var stuck := _group_move(sm, units, centre, t.position, 30.0)
		if not stuck.is_empty():
			# the walk to the target's side was refused (no path to that spot): send the capture
			# order itself, which finds its own way in (mc2_18 stood 15 min at 327 m)
			_order(sm, stuck[0], "capture", t)
			_stuck.erase(stuck[0].id)
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
			_goal.erase(capturer.id)
			# Jump-capture under the guns: "jump in and land next to the control building, hit
			# capture" [KC] (docs/research/original-missions.md, mc2_14).
			var spot: Vector2 = w.map.nearest_walkable(t.position + (capturer.position - t.position).normalized() * 20.0, capturer.hover)
			if capturer.order == SimWorld.Order.JUMP:
				pass
			elif capturer.distance_to(t.position) > 60.0 and not _covering(w, t.position).is_empty() \
					and w.jump_refusal(capturer, spot) == "":
				_order(sm, capturer, "jump", spot)
				if _verbose:
					print("t=%6.1f  JUMP %s to capture %s" % [w.time, capturer.name, t.name])
			else:
				_order(sm, capturer, "capture", t)
	var rest := units.filter(func(m): return m != capturer)
	_group_move(sm, rest, _centre(rest) if not rest.is_empty() else centre, t.position, 40.0)


## Pull a badly damaged mech out of the fight (to the repair truck if there is one, else behind
## the lance) while at least half the lance keeps fighting; back in once repaired or once the
## fight is over with no repair to be had. Extraction takes everyone. True if it is pulled back.
func _pull_back(sm: SimMission, m: SimUnit, lance: Array, centre: Vector2, threats: Array, task: Dictionary) -> bool:
	var w := sm.world
	var s: SimSupport = sm.support
	var trucks := _trucks(sm)
	var can_repair := not trucks.is_empty() or (s != null and s.rp >= int(SimSupport.COSTS["repair_truck"])) \
		or (s != null and s.delivering) or _bay_for(sm, m) != null
	var h := _health(m)
	if _retreat.has(m.id):
		if h >= RESUME_FRAC or (threats.is_empty() and not can_repair) or String(task.get("kind", "")) == "extract" \
				or not (m is SimMech and SimSupport.needs_refit(m)):
			_retreat.erase(m.id)
			return false
	elif m is SimMech and h < RETREAT_FRAC and (can_repair or not threats.is_empty()) and String(task.get("kind", "")) != "extract":
		var out := lance.filter(func(o): return _retreat.has(o.id)).size()
		if (out + 1) * 2 > lance.size() and not (_stealth and _bay_for(sm, m) != null):
			return false
		_retreat[m.id] = true
		if _verbose:
			print("t=%6.1f  PULLBACK %s at %.0f%%" % [w.time, m.name, 100.0 * h])
	else:
		return false
	_goal.erase(m.id)
	if _to_bay(sm, m):
		return true
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


## Our repair trucks that the lance can reach on foot (a truck dropped on the far side of a wall
## or water deadlocks a repair: neither it nor the mech can get to the other).
func _trucks(sm: SimMission) -> Array:
	var w := sm.world
	var lance := _lance(w)
	return w.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0 and not u.is_disabled() and u.exists \
		and (lance.is_empty() or _path_ok(sm, lance[0], u)))


## Active enemy turrets with guns (I99).
func _enemy_turrets(w: SimWorld) -> Array:
	if _turret_cache_t != w.time:
		_turret_cache_t = w.time
		_turret_cache = w.units.filter(func(u): return u is SimTurret and u.active and u.team != 0 and u.team >= 0 \
			and not u.is_destroyed() and u.num_weapons > 0)
		_reach_cache.clear()
	return _turret_cache


var _turret_cache_t := -1.0
var _turret_cache: Array = []
var _reach_cache := {}


## A turret's longest weapon reach, metres.
func _turret_reach(w: SimWorld, t: SimTurret) -> float:
	if _reach_cache.has(t.id):
		return _reach_cache[t.id]
	var r := 0.0
	for i in t.num_weapons:
		var wpn: Dictionary = t.items[i]["component"].get("weapon", {})
		r = maxf(r, float(w.rules.weapon_ranges[w.rules.range_index(wpn.get("range", "short"))][1]))
	_reach_cache[t.id] = minf(r, t.attack_m)
	return _reach_cache[t.id]


## Enemy turrets whose guns reach a point.
func _covering(w: SimWorld, p: Vector2) -> Array:
	return _enemy_turrets(w).filter(func(t): return t.position.distance_to(p) <= _turret_reach(w, t) + 15.0)


## The turret fort nearest the lance (turrets within 300 m): capture its control if we can, else
## destroy the control or generator it hangs on, else, for a turret with no control, shoot the
## turret itself (structures are always hit).
func _fort_job(sm: SimMission, lance: Array, centre: Vector2) -> Dictionary:
	var w := sm.world
	var near := _enemy_turrets(w).filter(func(t): return t.position.distance_to(centre) <= 300.0)
	if near.is_empty():
		return {}
	near.sort_custom(func(a, b): return a.position.distance_to(centre) < b.position.distance_to(centre))
	for t in near:
		var par: SimStructure = t.parent
		if par != null and par.exists and not par.is_destroyed():
			if par.position.distance_to(centre) > 600.0 or not _path_ok(sm, lance[0], par):
				continue
			# The control hangs on a generator that stands outside the guns: a destroyed (or asleep)
			# parent puts the control and its turrets to sleep (bldng.cpp:903-913, turret.cpp:620-633;
			# "kill the two generators ... to drop the HPG turrets" [KC, CB]).
			# (a control we can take is worth more: its turrets become ours; mc2_20 lost its fort
			# when the bot shot the generator instead, 2/3 -> 0/3)
			var gen: SimStructure = par.parent
			if not sm.abl.can_capture(par, 0) and gen != null and gen.exists and not gen.is_destroyed() and gen.team != 0 \
					and _covering(w, gen.position).size() < _covering(w, par.position).size() \
					and gen.position.distance_to(centre) <= 700.0:
				return {"kind": "attack", "target": gen}
			if sm.abl.can_capture(par, 0):
				return {"kind": "capture", "target": par}
			if par.team != 0:
				return {"kind": "attack", "target": par}
		elif par == null:
			return {"kind": "attack", "target": t}
	return {}


## Stall watch: a fight with no damage dealt for 150 s (enemies the lance can't reach or see)
## is dropped for 2 minutes, so the lance goes back to its objectives or extracts.
func _stall_watch(sm: SimMission, threats: Array) -> void:
	var w := sm.world
	if threats.is_empty() or _dealt > _stall_dealt + 0.5:
		_stall_dealt = _dealt
		_stall_since = w.time
		return
	if w.time - _stall_since < 150.0:
		return
	for t in threats:
		_ignore[t.id] = w.time + 120.0
	if _verbose:
		print("t=%6.1f  STALL no damage for %.0f s: leaving %d threats for 120 s" % [w.time, w.time - _stall_since, threats.size()])
	_stall_since = w.time


## A friendly repair bay with points left within reach of the mech, free or already fixing it.
func _bay_for(sm: SimMission, m: SimUnit) -> SimStructure:
	if sm.support == null or not (m is SimMech):
		return null
	var best: SimStructure = null
	for u in sm.world.units:
		if not (u is SimStructure) or not u.can_refit or not u.mech_bay or u.is_destroyed() or u.team != 0:
			continue
		if SimSupport.bay_points(u) <= 1.0 or u.distance_to(m.position) > (2000.0 if _stealth else 900.0):
			continue
		if u.refit_buddy != null and u.refit_buddy != m and u.refit_buddy.exists and not u.refit_buddy.is_disabled():
			continue
		if best == null or u.distance_to(m.position) < best.distance_to(m.position):
			best = u
	return best


## Send a damaged mech to a friendly bay (GETFIXED, support-powers.md 3.7); true while it is
## going there or being repaired.
func _to_bay(sm: SimMission, m: SimUnit) -> bool:
	var s: SimSupport = sm.support
	if s == null:
		return false
	if s.bay_repairs.any(func(r): return r["mech"] == m):
		return true
	var bay := _bay_for(sm, m)
	if bay == null or not SimSupport.needs_refit(m):
		return false
	if s.order_bay_repair(m, bay):
		if _verbose:
			print("t=%6.1f  BAY %s -> %s (%.0f m)" % [sm.world.time, m.name, bay.name, m.distance_to(bay.position)])
		return true
	return false


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
	for t in _covering(w, centre):  # fighting inside a fort's arcs (I99)
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
	# a lull near a friendly bay: the worst-hurt mech under 70% gets fixed there first
	var at_bay := false
	for m in units:
		if sm.support and sm.support.bay_repairs.any(func(r): return r["mech"] == m):
			at_bay = true
	if not at_bay:
		# a lone stealth mech tops up before every leg: it has no one to cover it
		var top := 0.85 if _stealth else RESUME_FRAC
		var hurt_b := units.filter(func(m): return m is SimMech and _health(m) < top and SimSupport.needs_refit(m) \
			and _bay_for(sm, m) != null and (_health(m) < RESUME_FRAC or _bay_for(sm, m).distance_to(m.position) <= 600.0))
		hurt_b.sort_custom(func(a, b): return _health(a) < _health(b))
		for m in hurt_b:
			if _to_bay(sm, m):
				at_bay = true
				break
	if at_bay:
		return true
	var trucks := _trucks(sm)
	var waiting := sm.support != null and sm.support.delivering and sm.support.pending.any(func(p): return p["kind"] == "vtol")
	if trucks.is_empty() and not waiting:
		return false
	var hurt := units.filter(func(m): return m is SimMech and _health(m) < RESUME_FRAC and SimSupport.needs_refit(m))
	if hurt.is_empty():
		return false
	var at: Vector2 = trucks[0].position if not trucks.is_empty() else _centre(units)
	if _trace and w.time - _lull_trace >= 30.0:
		_lull_trace = w.time
		for r in sm.support.repairs:
			print("t=%6.1f  LULL repair %s <- %s phase %s truck pool %.0f d %.0f truck order %d path %d; truck %s mech %s m->t path %d status %d" % [w.time, r["mech"].name,
				r["truck"].name, r["phase"], r["truck"].refit_pool, r["truck"].distance_to(r["mech"].position), r["truck"].order, r["truck"].path.size(),
				r["truck"].position, r["mech"].position, w.map.find_path(r["mech"].position, w.map.nearest_walkable(r["truck"].position)).size(), r["mech"].status])
		if sm.support.repairs.is_empty():
			print("t=%6.1f  LULL no repair running; hurt %s; trucks %d" % [w.time, hurt.map(func(m): return "%s %.0f%%" % [m.name, 100 * _health(m)]), trucks.size()])
	for r in sm.support.repairs:
		# the truck can't find a way to the mech (walls, water): the mech walks to the truck
		var tr: SimUnit = r["truck"]
		var rm: SimUnit = r["mech"]
		if r["phase"] == "drive" and tr.path.is_empty() and tr.distance_to(rm.position) > 60.0 \
				and (rm.order != SimWorld.Order.MOVE or rm.path.is_empty()):
			_order(sm, rm, "move", w.map.nearest_walkable(tr.position, rm.hover))
	for m in units:
		if sm.support.repairs.any(func(r): return r["mech"] == m):
			continue
		if m.distance_to(at) > 50.0 and (m.order != SimWorld.Order.MOVE or m.path.is_empty()):
			_order(sm, m, "move", w.map.nearest_walkable(at, m.hover))
			_goal.erase(m.id)
	return true


## Orders go through the lance's pbrain, as the player's do (CommandInput). The bot keeps
## Run on (the original's Space held): a player order walks otherwise (I82).
func _order(sm: SimMission, m: SimUnit, kind: String, arg: Variant, extra := {}) -> void:
	if sm.abl and m.brain is SimAbl.Pilot:
		var opts := {"run": true}
		opts.merge(extra, true)
		sm.abl.player_order(m, kind, arg, opts)
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
	if _rp_reserve > 0 and not _ready and kind != "repair_truck" and not (kind in ["artillery_piece", "minelayer"] and _prepping) \
			and sm.support.rp - int(SimSupport.COSTS.get(kind, 0)) < _rp_reserve:
		return false  # RP kept for the reception (ROUTE_PLANS "rp_reserve")
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
	var trucks := _trucks(sm)
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
		var drop := w.map.nearest_walkable(at)
		if w.map.find_path(hurt[0].position, drop, hurt[0].hover).is_empty():
			drop = w.map.nearest_walkable(hurt[0].position)  # on the mech's side of any wall
		if _support(sm, "repair_truck", drop):
			return
	var striking := s.pending.filter(func(p): return p["kind"] == "strike" and int(p.get("team", 0)) == sm.player_team)
	# Switch a fort off from outside it: an air strike (3 x 15 at the centre) destroys a generator
	# or control of 45 DmgLevel or less, and its turrets go to sleep (bldng.cpp:903-913,
	# turret.cpp:620-633). For a root under its own guns that the lance would otherwise have to
	# walk into (mc2_22's drop is boxed in by two turret lines: "First disable or capture the
	# northern defenses. THEN use that to get out" [KC]).
	if _fort_strike and s.can_call("air_strike") and s.rp - int(SimSupport.COSTS["air_strike"]) >= reserve and w.time - _last_strike >= 12.0:
		var roots := {}
		for t in _enemy_turrets(w):
			if t.position.distance_to(centre) > 500.0 or t.parent == null:
				continue
			var root: SimStructure = t.parent
			if root.parent != null and not root.parent.is_destroyed() and root.parent.awake:
				root = root.parent
			if root.is_destroyed() or root.team == 0 or root.damage_level > 3.0 * SimSupport.STRIKE_DAMAGE:
				continue
			roots[root] = int(roots.get(root, 0)) + 1
		var pick: SimStructure = null
		for r in roots:
			if _covering(w, r.position).is_empty() or int(roots[r]) < 3:
				continue  # walkable to, or too small a fort to spend a strike on
			if w.units.any(func(u): return u.team == 0 and u.exists and not u.is_destroyed() and u.position.distance_to(r.position) <= STRIKE_GUARD_M):
				continue
			if striking.any(func(p): return (p["at"] as Vector2).distance_to(r.position) < 30.0):
				continue
			if pick == null or int(roots[r]) > int(roots[pick]):
				pick = r
		if pick != null and _support(sm, "air_strike", pick.position):
			_last_strike = w.time
			if _verbose:
				print("t=%6.1f  FORT STRIKE on %s (%d turrets hang on it)" % [w.time, pick.name, roots[pick]])
			return
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
	# Long Toms against bunched enemies (players drop 2-4 to break waves, research doc): a piece
	# behind the lance when three or more armed enemies are near and RP covers a truck as well;
	# and against a turret fort, shelled from outside its guns' reach (I99).
	var guns := w.units.filter(func(u): return u.team == 0 and u.model == "artillerypiece" and u.exists and not u.is_disabled())
	var forts := _enemy_turrets(w).filter(func(t): return t.position.distance_to(centre) <= 260.0)
	for g in guns:  # an idle gun shells the nearest turret it can reach (indirect fire on our sight)
		if g.order != SimWorld.Order.ATTACK and threats.filter(func(e): return e.distance_to(g.position) <= 180.0).is_empty():
			var tt := _enemy_turrets(w).filter(func(t): return t.position.distance_to(g.position) <= 175.0 and t.position.distance_to(g.position) > 65.0)
			if not tt.is_empty():
				tt.sort_custom(func(a, b): return a.position.distance_to(g.position) < b.position.distance_to(g.position))
				w.order_attack(g, tt[0], false, false)
	if s.can_call("artillery_piece") and guns.size() < 2 and forts.size() >= 2 and threats.is_empty() \
			and s.rp - int(SimSupport.COSTS["artillery_piece"]) >= reserve:
		var fc := _centre(forts)
		var spot := fc + (centre - fc).normalized() * 160.0  # in Long Tom reach, out of most turret guns
		if _covering(w, spot).is_empty() and _support(sm, "artillery_piece", w.map.nearest_walkable(spot)):
			return
	if s.can_call("artillery_piece") and guns.size() < 3 and threats.size() >= 3 \
			and s.rp - int(SimSupport.COSTS["artillery_piece"]) >= reserve \
			and not guns.any(func(g): return g.position.distance_to(centre) < 150.0):
		var back := centre + (centre - _centre(threats)).normalized() * 50.0
		if _support(sm, "artillery_piece", w.map.nearest_walkable(back)):
			return
	if s.can_call("sensor_probe") and threats.is_empty() and s.probes.is_empty() \
			and w.time > 30.0 and s.rp >= int(SimSupport.COSTS["sensor_probe"]) + 2 * int(SimSupport.COSTS["repair_truck"]) + int(SimSupport.COSTS["air_strike"]):
		var task := _task(sm, lance, centre)
		var goal: Variant = task.get("area", (task["target"] as SimUnit).position if task.has("target") else null)
		if goal != null and centre.distance_to(goal) > 500.0:
			_support(sm, "sensor_probe", centre + (goal - centre).normalized() * 450.0)


func _play(sm: SimMission, max_t: float, args: PackedStringArray, verbose: bool, mission := "") -> void:
	var w := sm.world
	var o := sm.objectives
	var next_order := 0.0
	_trace = "--trace" in args
	_fort_strike = not ("--no-fort-strike" in args)
	_bombs = not ("--no-bombs" in args)
	_unlocks = not ("--no-unlock" in args)
	_stealth = STEALTH_PLANS.has(mission)
	_quiet_spot = null
	_first = STEALTH_PLANS.get(mission, ROUTE_PLANS.get(mission, {})).get("first", [])
	_arcs = bool(ROUTE_PLANS.get(mission, {}).get("arcs", false))
	var rp_plan: Dictionary = ROUTE_PLANS.get(mission, {})
	_spare = int(rp_plan.get("spare", -1))
	_via = (rp_plan.get("via", []) as Array).duplicate()
	_follow = int(rp_plan.get("follow", -1))
	_run_out = bool(rp_plan.get("run_out", false))
	_follow_since = -1.0
	_prep_at = rp_plan.get("prep_at")
	_prep_guns = int(rp_plan.get("prep_guns", 0))
	_mine_segs = (rp_plan.get("mines", []) as Array).duplicate(true)
	_mines_called = false
	_mine_at_start = false
	_rp_reserve = int(rp_plan.get("rp_reserve", 0))
	_spared = null
	_ready = false
	var plan: Dictionary = HOLD_PLANS.get(mission, {})
	_hold_at = null
	_hold_reached = false
	_hold_pending = {}
	if plan.has("after"):
		_hold_pending = plan
	_hold_watch = float(plan.get("watch", 700.0))
	_hold_decoy = bool(plan.get("decoy", false))
	_lure_mechs = bool(plan.get("lure_mechs", false))
	_lure_s = float(plan.get("lure_s", 90.0))
	if plan.has("at_start"):
		_hold_at = _centre(_lance(sm.world))
		_hold_r = float(plan["radius"])
		_hold_q = float(plan["quiet"])
	for obj in sm.objectives.objectives:
		if not plan.is_empty() and int(obj["index"]) == int(plan.get("objective", -1)):
			for c in obj["conditions"]:
				if c.has("center"):
					_hold_at = c["center"]
					_hold_r = float(plan["radius"])
					_hold_q = float(plan["quiet"])
	for a in args:
		if a.begins_with("--shots="):
			_shots_left = int(a.trim_prefix("--shots="))
	var gone_since := -1.0
	while w.time < max_t and o.result == SimObjectives.Result.PLAYING:
		sm.step()
		# Harness rule (I13): with no armed unit of the lance left, only support vehicles keep the
		# mission open (B6); a player has lost then. Stop and score it a loss after 30 s.
		if int(w.time * 10.0) % 10 == 0:
			# an immobile artillery piece can't finish anything either
			if _lance(w).is_empty() and not w.units.any(func(u): return u.is_mover() and u.team == 0 and u.commander == 0 \
					and u.is_disabled() == false and u.on_gui and u.num_weapons > 0 and u.run_speed > 0.0):
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
				"captured", "capture_blocked", "capture_refused", "turret_team", "turret_down", "repair_done", "mine":
					if verbose and (_trace or e["type"] in ["captured", "turret_down", "repair_done"]):
						var who: String = w.units[e["unit"]].name if int(e.get("unit", -1)) >= 0 else "-"
						var what: String = w.units[e["target"]].name if e.has("target") else (w.units[e["bay"]].name if e.has("bay") else "")
						var by: String = (" by " + w.units[e["by"]].name + " (" + w.units[e["by"]].brain_name + ")") if e.has("by") else ""
						print("t=%6.1f  %s %s %s%s" % [w.time, String(e["type"]).to_upper(), who, what, by])
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
					elif victim.team == 0 and victim.commander == 0:
						# no source unit: an air strike (whose team called it, I114) or an unowned blast
						var what := "Air strike (%s)" % ("ours" if int(e.get("team", -1)) == 0 else "enemy") \
							if String(e.get("form", "")) == "strike" else "Explosion (%s)" % e.get("form", "?")
						_damage[what] = _damage.get(what, 0.0) + float(e.get("damage", 0.0))
						var loc2 := int(e.get("location", -1))
						_locs[loc2] = _locs.get(loc2, 0) + 1
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
			_play(sm, max_t, PackedStringArray(), false, m)
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
