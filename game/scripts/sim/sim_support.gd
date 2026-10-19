class_name SimSupport
extends RefCounted
## The player's in-mission support powers, paid for with Resource Points (RP), and the
## enemy aerospace spotter's strikes. Behaviour follows docs/specs/support-powers.md
## (section numbers below refer to it).
##
## Implemented: air strike (3.1), sensor probe (3.2), repair truck via VTOL delivery
## (3.3, 3.4), salvage craft (3.6), RP gains on capture (1), spotter strikes (5).
## Not yet: minelayer, scout copter, artillery piece (their unit data isn't converted).
## Simplifications: no line-of-sight model, so an air strike is always the big one;
## the cost is charged when the target is placed rather than on the button press
## (same outcome: the original refunds a cancelled call); deliveries appear without
## the VTOL / Karnov animations.

const COSTS := {"air_strike": 7000, "sensor_probe": 2000, "repair_truck": 6000, "salvage_craft": 10000}
const ORDER := ["air_strike", "sensor_probe", "repair_truck", "salvage_craft"]
const LABELS := {"air_strike": "Air strike", "sensor_probe": "Sensor probe", "repair_truck": "Repair truck",
	"salvage_craft": "Salvage craft"}
const DELIVERIES := ["repair_truck", "salvage_craft"]  # one VTOL / Karnov at a time (2)

const STRIKE_DELAY := 7.0
const STRIKE_REACH_M := 37.4  # 187 wu: strike extent; plus the target's own (3.1)
const STRIKE_MAJOR_M := 25.0
const STRIKE_DAMAGE := 15.0
const STRIKE_MAJOR_HITS := 3
const STRIKE_MINOR_HITS := 2
const PROBE_RADIUS_M := 800.0
const PROBE_LIFE := 120.0
const VTOL_SPAWN := 4.8
const VTOL_DONE := 10.0
const REFIT_RANGE_M := 30.0
const REFIT_POWERDOWN := 3.0
const REFIT_PERIOD := 1.0
const REFIT_POINTS := 10.0
const SALVAGE_TIME := 4.8 + 5.0
const SPOTTER_PERIOD := 10.0
const SPOTTER_RANGE_M := 120.0
const SPOTTER_DELAY := 4.0

var sm: SimMission
var world: SimWorld
var rp := 0
var pending: Array[Dictionary] = []  # strikes, deliveries, salvage in progress
var probes: Array[Dictionary] = []  # {pos, t0}
var repairs: Array[Dictionary] = []  # {truck, mech, phase, next}
var delivering := false
var _spotter_next := {}  # spotter id -> next strike time
var _next_reinforcement_id := 2050  # runtime part IDs (abl-natives.md 1.2)


static func create(mission: SimMission) -> SimSupport:
	var s := SimSupport.new()
	s.sm = mission
	s.world = mission.world
	s.rp = int(mission.fit.get("MissionSettings", {}).get("ResourcePoints", 0))
	return s


func can_call(kind: String) -> bool:
	return rp >= int(COSTS.get(kind, 1 << 30)) and not (kind in DELIVERIES and delivering)


## Valid target for a power: a ground point (Vector2, metres) or, for the salvage
## craft, a disabled (not destroyed) mech of any team.
func valid_target(kind: String, target: Variant) -> bool:
	if kind == "salvage_craft":
		return target is SimMech and target.is_disabled() and not target.is_destroyed() and target.exists
	return target is Vector2


## Place a power; false if it can't be afforded, a delivery is in flight, or the
## target is wrong. Emits {"type": "support", ...} for the view.
func call_power(kind: String, target: Variant) -> bool:
	if not can_call(kind) or not valid_target(kind, target):
		return false
	rp -= int(COSTS[kind])
	var t := world.time
	match kind:
		"air_strike":
			pending.append({"kind": "strike", "at": target, "impact": t + STRIKE_DELAY, "team": sm.player_team})
		"sensor_probe":
			probes.append({"pos": target, "t0": t})
		"repair_truck":
			delivering = true
			pending.append({"kind": "vtol", "vehicle": "repairtruck", "at": world.map.nearest_walkable(target),
				"spawn": t + VTOL_SPAWN, "done": t + VTOL_DONE, "unit": null})
		"salvage_craft":
			delivering = true
			pending.append({"kind": "salvage", "target": target, "done": t + SALVAGE_TIME})
	world.events.append({"type": "support", "kind": kind,
		"at": target if target is Vector2 else (target as SimUnit).position})
	return true


## A selected repair truck services a damaged friendly mech (3.4).
func order_repair(truck: SimUnit, mech: SimUnit) -> bool:
	if truck.refit_pool <= 0.0 or truck.is_disabled() or not (mech is SimMech) or mech.is_disabled() \
			or mech.team != truck.team or not needs_refit(mech):
		return false
	for r in repairs:
		if r["truck"] == truck or r["mech"] == mech:
			if r["truck"] == truck and r["mech"] == mech:
				return true
			_end_repair(r)
	repairs.append({"truck": truck, "mech": mech, "phase": "drive", "next": 0.0})
	world.order_move(truck, mech.position)
	return true


static func needs_refit(m: SimMech) -> bool:
	for loc in m.armor.size():
		var body: int = SimMech.ARMOR_TO_BODY[loc]
		if _arm_gone(m, body):
			continue
		if m.armor[loc] < m.max_armor[loc] - 0.01 or m.internal[body] < m.max_internal[body] - 0.01:
			return true
	return false


static func _arm_gone(m: SimMech, body: int) -> bool:
	return body in [SimMech.Body.LARM, SimMech.Body.RARM] and m.damage_state[body] == SimMech.DamageState.DESTROYED


# --- per tick ---------------------------------------------------------------------------

func step() -> void:
	var t := world.time
	var still: Array[Dictionary] = []
	for p in pending:
		match p["kind"]:
			"strike":
				if t >= p["impact"]:
					_strike(p["at"])
					continue
			"vtol":
				if p["unit"] == null and t >= p["spawn"]:
					p["unit"] = _spawn_vehicle(p["vehicle"], p["at"])
				if t >= p["done"]:
					delivering = false
					continue
			"salvage":
				if t >= p["done"]:
					_salvage(p["target"])
					delivering = false
					continue
		still.append(p)
	pending = still
	probes = probes.filter(func(pr): return t - float(pr["t0"]) < PROBE_LIFE)
	for r in repairs.duplicate():
		_repair_step(r)
	_spotters()


func probe_covers(team: int, pos: Vector2) -> bool:
	if team != sm.player_team:
		return false
	for pr in probes:
		var radius := PROBE_RADIUS_M * (1.0 - (world.time - float(pr["t0"])) / PROBE_LIFE)
		if pos.distance_to(pr["pos"]) <= radius:
			return true
	return false


# --- air strike (3.1) ---------------------------------------------------------------------

func _strike(at: Vector2) -> void:
	world.events.append({"type": "strike_impact", "at": at})
	for u in world.units:
		if not u.exists or u.is_destroyed():
			continue
		var extent := (u as SimStructure).extent_m if u is SimStructure else 0.0
		var d := u.position.distance_to(at)
		if d > STRIKE_REACH_M + extent:
			continue
		var hits := STRIKE_MAJOR_HITS if d <= STRIKE_MAJOR_M else STRIKE_MINOR_HITS
		for i in hits:
			var loc: int
			if u is SimMech:
				loc = SimCombat.hit_location(world.rules, world.rng, u, at)
			else:
				loc = u.roll_hit_location(world.rules, world.rng, at)
			SimCombat.apply_shot(world.rules, world.rng, u, {"hit": true, "damage": STRIKE_DAMAGE, "location": loc,
				"master_id": -3}, world.time)
			world.events.append({"type": "impact", "unit": u.id, "from": -1, "location": loc, "damage": STRIKE_DAMAGE, "form": "strike"})


## The enemy aerospace spotter calls a big strike every 10 s on a player unit within
## 120 m, landing 4 s later (5).
func _spotters() -> void:
	for u in world.units:
		if not (u is SimVehicle) or u.model != "aerospotter" or u.team == sm.player_team or not u.exists or u.is_disabled():
			continue
		if world.time < float(_spotter_next.get(u.id, 0.0)):
			continue
		var best: SimUnit = null
		var best_d := SPOTTER_RANGE_M
		for m in world.units:
			if m.team == sm.player_team and m.is_mover() and m.exists and not m.is_disabled():
				var d := m.position.distance_to(u.position)
				if d <= best_d:
					best = m
					best_d = d
		if best:
			_spotter_next[u.id] = world.time + SPOTTER_PERIOD
			pending.append({"kind": "strike", "at": best.position, "impact": world.time + SPOTTER_DELAY, "team": u.team})
			world.events.append({"type": "support", "kind": "air_strike", "at": best.position, "enemy": true})


# --- deliveries (3.3) --------------------------------------------------------------------

func _spawn_vehicle(file: String, at: Vector2) -> SimUnit:
	var path := "res://data/vehicles/%s.json" % file
	if not FileAccess.file_exists(path):
		return null
	var v := SimVehicle.from_data(JSON.parse_string(FileAccess.get_file_as_string(path)), world.rules, SimPilot.make(50, 50))
	v.team = sm.player_team
	v.commander = 0
	v.is_player = true
	v.position = at
	v.facing = 0.0
	v.part_id = _next_reinforcement_id
	_next_reinforcement_id += 1
	world.add_unit(v)
	world.events.append({"type": "unit_added", "unit": v.id})
	return v


# --- repair truck (3.4) -------------------------------------------------------------------

func _repair_step(r: Dictionary) -> void:
	var truck: SimUnit = r["truck"]
	var mech: SimMech = r["mech"]
	if truck.is_disabled() or not truck.exists or mech.is_disabled() or not mech.exists:
		_end_repair(r)
		return
	var t := world.time
	match r["phase"]:
		"drive":
			if truck.distance_to(mech.position) <= REFIT_RANGE_M:
				world.order_hold(truck)
				world.order_hold(mech)
				mech.status = SimUnit.Status.SHUTDOWN
				r["phase"] = "power_down"
				r["next"] = t + REFIT_POWERDOWN
			elif truck.order == SimWorld.Order.HOLD or truck.position.distance_to(mech.position) > REFIT_RANGE_M * 3.0 and truck.path.is_empty():
				world.order_move(truck, mech.position)
		"power_down", "refit":
			if t < float(r["next"]):
				return
			r["phase"] = "refit"
			r["next"] = t + REFIT_PERIOD
			truck.refit_pool -= _refit_cycle(mech, minf(REFIT_POINTS, truck.refit_pool))
			if not needs_refit(mech) or truck.refit_pool <= 0.0:
				if truck.refit_pool <= 0.0:
					truck.refit_pool = 0.0
					truck.status = SimUnit.Status.DISABLED  # spent: POWER_USED_UP
				world.events.append({"type": "repair_done", "unit": mech.id, "truck": truck.id})
				_end_repair(r)


func _end_repair(r: Dictionary) -> void:
	var mech: SimUnit = r["mech"]
	if mech.status == SimUnit.Status.SHUTDOWN and not mech.powered_down:
		mech.status = SimUnit.Status.NORMAL
	repairs.erase(r)


## One refit cycle (3.4.1): about 10 points spread evenly over the deficit slots.
## Returns the points used.
static func _refit_cycle(m: SimMech, budget: float) -> float:
	var slots := []
	for loc in m.armor.size():
		var body: int = SimMech.ARMOR_TO_BODY[loc]
		if _arm_gone(m, body):
			continue
		if m.armor[loc] < m.max_armor[loc]:
			slots.append(["armor", loc])
		if loc < SimMech.ARMOR_TO_BODY.size() and loc == body and m.internal[body] < m.max_internal[body]:
			slots.append(["internal", body])
	if slots.is_empty() or budget <= 0.0:
		return 0.0
	var each := budget / slots.size()
	var used := 0.0
	for s in slots:
		if s[0] == "armor":
			var add := minf(each, m.max_armor[s[1]] - m.armor[s[1]])
			m.armor[s[1]] += add
			used += add
		else:
			var add := minf(each, m.max_internal[s[1]] - m.internal[s[1]])
			m.internal[s[1]] += add
			used += add
			m._update_damage_state(s[1])
	return maxf(snappedf(used, 0.25), 0.25)


# --- salvage craft (3.6) ------------------------------------------------------------------

func _salvage(m: SimMech) -> void:
	if m == null or not m.exists or m.is_destroyed():
		rp += int(COSTS["salvage_craft"])  # the craft leaves empty-handed: refunded
		return
	for body in m.internal.size():
		if not _arm_gone(m, body):
			m.internal[body] = m.max_internal[body]
			m._update_damage_state(body)
	for item in m.items:
		item["health"] = 1
		item["disabled"] = false
	for body in m.crit_hit.size():
		for slot in m.crit_hit[body].size():
			m.crit_hit[body][slot] = false
	m.fallen = false
	m.failed_piloting_check = false
	m.fall_time = -1.0
	m.engine_blow_time = -1.0
	m.ejected = false
	m.reported_disabled = false
	m.status = SimUnit.Status.NORMAL
	m.team = sm.player_team
	m.commander = 0
	m.is_player = true
	m.pilot = SimPilot.make(50, 50)
	m.current_target = null
	world.order_hold(m)
	if m.part_id < 512:
		m.part_id = _next_reinforcement_id
		_next_reinforcement_id += 1
	if sm.abl:
		sm.abl.add_pilot(m, "pbrain")
	world.events.append({"type": "salvaged", "unit": m.id})
