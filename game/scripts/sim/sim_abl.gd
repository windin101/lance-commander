class_name SimAbl
extends RefCounted
## Runs a mission's original ABL against the sim: the mission script (every step)
## and each unit's brain (every 2.25 s, staggered), with the game natives the
## scripts call implemented on SimWorld. Behaviour follows docs/specs/abl-natives.md
## (section numbers below refer to it).
##
## Positions cross the boundary in original world units (metres / 0.2); distances
## the natives take or return are metres. Objects are addressed by ABL part ID (1).
##
## Simplifications against the original, each noted where it applies:
## - Contacts: a team's contacts are the hostile movers within SENSOR_M of any of its
##   awake movers. There is no separate visual/sensor model yet.
## - Tactical orders run directly on SimWorld orders (no goal planner, 2.1).
## - Presentation natives (music, voice, video, camera, movie mode) emit world
##   events of type "abl_*" for the view; their return values follow the spec.

const BRAIN_PERIOD := 2.25
const BRAIN_STAGGER := 0.2
const WU := 0.2  # metres per world unit
const SENSOR_M := 500.0
const MAX_TRIGGERS := 15

# PILOT_EVENT_*
const EV_TARGETED := 0
const EV_HIT := 1
const EV_FRIENDLY_KILLED := 3
const EV_ATTACK_ORDER := 9
const EV_TARGET_KILLED := 12
const EV_MATE_FIRED := 13
const EV_FIRED_WEAPON := 17
const EV_PLAYER_ORDER := 14
# Alarm handler functions the engine calls the moment an alarm is raised (2.5).
const HANDLERS := {0: "handletargetofweaponfire", 1: "handlehitbyweaponfire", 2: "handledamagetakenrate",
	3: "handledeathofmate", 4: "handlecripplingoffriendlyvehicle", 5: "handledestructionoffriendlyvehicle",
	6: "handleincapacitationofvehicle", 7: "handledestructionofvehicle", 8: "handlewithdraw",
	9: "handleattackorder", 10: "handlecollision", 11: "handleguardbreach", 12: "handlekilledtarget",
	13: "handlematefiredweapon", 14: "handleplayerorder", 15: "handlenomovepath", 16: "handlegateclosing",
	17: "handlefiredweapon", 18: "handlenewmover"}
# TACTICAL_ORDER_*
const TO_NONE := 0
const TO_WAIT := 1
const TO_MOVETO_POINT := 2
const TO_MOVETO_OBJECT := 3
const TO_STOP := 11
const TO_POWERUP := 12
const TO_POWERDOWN := 13
const TO_EJECT := 15
const TO_ATTACK_OBJECT := 16
const TO_CAPTURE := 21
const CAPTURE_M := 30.0  # capture happens on arrival this close (capture-and-objectives.md A2)
const BLOCK_CAPTURE_M := 75.0  # gamesys BlockCaptureRange: an armed enemy this close to the target blocks it
# TACORDER_PARAM_*
const P_RUN := 1
const P_PURSUE := 16
const P_OBLITERATE := 32
const P_DONT_SET_ORDER := 524288
const P_STOP_AND_FIRE := 33554432
const P_TURRET := 67108864
# CONTACT_CRITERIA_*
const C_ENEMY := 1
const C_NOT_CHALLENGED := 8
const C_NOT_DISABLED := 64
const C_ARMED := 128

var sm: SimMission
var world: SimWorld
var runtime: AblRuntime
var mission_inst: AblRuntime.Instance
var pilots: Array = []
var script_result := 0  # last value the mission script returned (scenario result, 4)
var music_id := -1
var trigger_areas: Dictionary = {}  # handle -> {r1, c1, r2, c2, type, param, hit}
var _next_area := 1
var _by_part: Dictionary = {}  # part ID -> SimUnit
var _logistics_ms := 0.0
var current: Pilot = null  # the pilot whose brain is running (2.3)
var voice_busy: Callable  # the view: is a voice-over or comms clip still playing (isPlayingVoiceOver)


class Pilot:
	extends RefCounted
	var abl: SimAbl
	var unit: SimUnit
	var inst: AblRuntime.Instance
	var next_brain := 0.0
	var cells: Array = []  # 60 memory cells (2.8); ints and floats share a slot
	var priorities: Array = []  # [{type, p1, p2, p3}] (2.6)
	var history: Dictionary = {}  # event code -> [trigger part IDs] since the last brain run
	var cursor := -1
	var last_scan: SimUnit = null
	var will_help := true
	var challenger: SimUnit = null
	var move_area := {}  # {"centre": Vector2 m, "radius": m}
	var order := {"code": TO_NONE}
	var debug: Array = ["", "", "", "", ""]
	var pending: Array = []  # alarm codes raised since the handlers last ran
	var alarm := -1  # the alarm whose handler is running (getAlarmTriggers)

	func think(_world: SimWorld, u: SimUnit) -> void:
		abl._pilot_tick(self, u)

	func raise(code: int, trigger: int) -> void:
		var list: Array = history.get(code, [])
		if list.size() < MAX_TRIGGERS:
			list.append(trigger)
		history[code] = list
		if not pending.has(code):
			pending.append(code)


static func attach(mission: SimMission, name: String) -> SimAbl:
	var path := "res://data/abl/%s.abl" % name
	if not FileAccess.file_exists(path):
		return null
	var a := SimAbl.new()
	a.sm = mission
	a.world = mission.world
	a.runtime = AblRuntime.new("res://data/abl", mission.seed)
	a._register()
	for u in a.world.units:
		if u.part_id > 0:
			a._by_part[u.part_id] = u
	a.mission_inst = a.runtime.instantiate(name + ".abl")
	var fit: Dictionary = mission.fit
	for u in a.world.units:
		if not u.is_mover() or u.brain_name == "":
			continue
		var p := a.add_pilot(u, u.brain_name)
		if p == null:
			continue
		var w: Dictionary = fit.get("Warrior%d" % u.warrior_index, {})
		for j in int(w.get("NumCells", 0)):
			var c: Dictionary = fit.get("Warrior%dCell%d" % [u.warrior_index, j], {})
			var idx := int(c.get("Cell", -1))
			if idx >= 0 and idx < 60:
				p.cells[idx] = float(c.get("Value", 0)) if int(c.get("MemType", 0)) == 1 else int(c.get("Value", 0))
	return a


## Give a unit its ABL brain (at load, or later: a salvaged mech gets pbrain).
func add_pilot(u: SimUnit, brain: String) -> Pilot:
	var inst := runtime.instantiate("warriors/%s.abl" % brain.to_lower().trim_suffix(".abl"))
	if inst == null:
		return null
	var p := Pilot.new()
	p.abl = self
	p.unit = u
	p.inst = inst
	inst.host = p
	p.cells.resize(60)
	p.cells.fill(0)
	p.next_brain = world.time + (pilots.size() % 30) * BRAIN_STAGGER
	u.brain = p
	u.brain_name = brain
	pilots.append(p)
	if u.part_id > 0:
		_by_part[u.part_id] = u
	if brain.to_lower() == "pbrain":
		u.engage_m = 100.0  # pbrain Init: SetEngageRadius(100)
	return p


# --- per tick ---------------------------------------------------------------------------

func _pilot_tick(p: Pilot, u: SimUnit) -> void:
	if u.ejected or not u.awake:
		return
	_order_progress(p, u)
	if world.time >= p.next_brain:
		p.next_brain += BRAIN_PERIOD
		current = p
		p.cursor = -1
		p.inst.execute()
		current = null
		p.history.clear()


## After SimWorld.step: derive pilot events from the new world events, latch trigger
## areas, run the mission script.
func after_step(new_events: Array) -> void:
	for e in new_events:
		match e["type"]:
			"shot":
				var from := world.units[e["from"]]
				var to := world.units[e["to"]]
				_raise(to, EV_TARGETED, from.part_id)
				_raise(from, EV_FIRED_WEAPON, to.part_id)
				for mate in _group_mates(from):
					if mate != from:
						_raise(mate, EV_MATE_FIRED, from.part_id)
			"impact":
				var from_id: int = int(e.get("from", -1))
				if from_id >= 0:
					_raise(world.units[e["unit"]], EV_HIT, world.units[from_id].part_id)
			"disabled":
				var victim := world.units[e["unit"]]
				if victim.last_attacker:
					_raise(victim.last_attacker, EV_TARGET_KILLED, victim.part_id)
				if victim.is_mover():
					for mate in _group_mates(victim):
						if mate != victim:
							_raise(mate, EV_FRIENDLY_KILLED, victim.part_id)
	for h in trigger_areas:
		var a: Dictionary = trigger_areas[h]
		if a["hit"]:
			continue
		for u in world.units:
			if u.is_mover() and u.exists and not u.is_disabled() and _area_matches(a, u):
				var c := world.map.cell_of(u.position)
				if c.y >= a["r1"] and c.y < a["r2"] and c.x >= a["c1"] and c.x < a["c2"]:
					a["hit"] = true
					break
	run_alarm_handlers()
	_logistics_ms += SimWorld.TICK * 1000.0
	if mission_inst:
		script_result = int(AblRuntime._num(mission_inst.execute()))
		# Mirror the mission's boolean eternals (its flags) into world.flags, lowercased,
		# for the view's cues and for tests.
		var et: Dictionary = mission_inst.unit["_eternals"]
		for n in et:
			if et[n] is bool:
				world.flags[n] = et[n]


## Call each pilot's handler for the alarms raised since the last call (2.5); only
## pbrain defines handlers in the campaign.
func run_alarm_handlers() -> void:
	for p in pilots:
		if p.pending.is_empty():
			continue
		var codes: Array = p.pending.duplicate()
		p.pending.clear()
		if p.unit.is_disabled() or p.unit.ejected:
			continue
		for code in codes:
			var h: String = HANDLERS.get(code, "")
			if h != "" and runtime.has_function(p.inst, h):
				current = p
				p.alarm = code
				runtime.call_function(p.inst, h)
				p.alarm = -1
				current = null


## A command from the player (CommandInput): becomes the pilot's tactical order with
## player origin, then raises PLAYER_ORDER so pbrain's handler sees it at once.
## kind: "move" (arg: goal Vector2 m), "attack" (arg: SimUnit), "capture" (arg: SimUnit), "stop".
func player_order(u: SimUnit, kind: String, arg: Variant = null) -> void:
	if not (u.brain is Pilot):
		return
	var p: Pilot = u.brain
	var o: Dictionary
	match kind:
		"capture":
			var t: SimUnit = arg
			if not can_capture(t, u.team) or capture_blocker(t, u, false) != null:
				world.events.append({"type": "capture_refused", "unit": u.id, "target": t.id})
				return
			o = {"code": TO_CAPTURE, "target": t, "goal": _capture_goal(u, t), "origin": 0}
		"move":
			o = {"code": TO_MOVETO_POINT, "goal": arg, "run": true, "origin": 0}
		"attack":
			o = {"code": TO_ATTACK_OBJECT, "target": arg, "pursue": true, "origin": 0}
		_:
			o = {"code": TO_STOP, "origin": 0}
	if int(o["code"]) == TO_STOP:
		p.order = {"code": TO_NONE}
		world.order_hold(u)
	else:
		_issue(p, o)
	p.raise(EV_PLAYER_ORDER, int(o["code"]))
	run_alarm_handlers()


func _raise(u: SimUnit, code: int, trigger: int) -> void:
	if u.brain is Pilot:
		u.brain.raise(code, trigger)


func _area_matches(a: Dictionary, u: SimUnit) -> bool:
	match int(a["type"]):
		1:
			return int(a["param"]) <= 0 or u.part_id == int(a["param"])
		2:
			return u.team == int(a["param"]) or 500 + u.team == int(a["param"])
		3:
			return u.group == int(a["param"])
		4:
			return u.commander == int(a["param"])
	return false


# --- tactical orders (2.7) ------------------------------------------------------------

func _order_progress(p: Pilot, u: SimUnit) -> void:
	var o := p.order
	if _order_done(p, u, o):
		p.order = {"code": TO_NONE}


func _order_done(p: Pilot, u: SimUnit, o: Dictionary) -> bool:
	match int(o["code"]):
		TO_WAIT:
			return world.time > float(o.get("end", 0.0))
		TO_MOVETO_POINT, TO_MOVETO_OBJECT:
			return world.map.cell_of(u.position) == world.map.cell_of(o["goal"])
		TO_ATTACK_OBJECT:
			var t: SimUnit = o.get("target")
			return t == null or not t.exists or t.is_destroyed() or (t.is_disabled() and not o.get("obliterate", false))
		TO_POWERUP:
			return u.status == SimUnit.Status.NORMAL
		TO_CAPTURE:
			return _capture_step(p, u, o)
		TO_EJECT:
			return true
	return false


func _issue(p: Pilot, o: Dictionary) -> void:
	var u := p.unit
	p.order = o
	match int(o["code"]):
		TO_MOVETO_POINT, TO_MOVETO_OBJECT, TO_CAPTURE:
			world.order_move(u, o["goal"])
		TO_ATTACK_OBJECT:
			var t: SimUnit = o["target"]
			u.current_target = t
			if o.get("pursue", true):
				world.order_attack(u, t)
			else:
				world.order_hold(u)
		TO_WAIT:
			world.order_hold(u)


func _same_order(p: Pilot, o: Dictionary) -> bool:
	var c := p.order
	if int(c["code"]) != int(o["code"]):
		return false
	match int(o["code"]):
		TO_MOVETO_POINT, TO_MOVETO_OBJECT:
			return world.map.cell_of(c["goal"]) == world.map.cell_of(o["goal"])
		TO_ATTACK_OBJECT:
			return c.get("target") == o.get("target") and c.get("pursue") == o.get("pursue")
	return true


# --- capture (capture-and-objectives.md A2-A4) ------------------------------------------

## isCaptureable: flagged, not already the team's, not destroyed, still in play.
func can_capture(t: SimUnit, team: int) -> bool:
	# Mechs can't be taken by a capture order (only salvaged), so "capture or destroy"
	# a mech means disable it (A1).
	return t != null and not (t is SimMech) and t.capturable and t.exists and t.team != team \
		and not t.is_destroyed() and not t.hulk


## An armed, awake, enemy mover within 75 m of the target, or null. Before arrival
## (near = false) the capturer's team must also see it; on arrival it needn't.
func capture_blocker(t: SimUnit, capturer: SimUnit, near: bool) -> SimUnit:
	for m in world.units:
		if not m.is_mover() or not m.exists or m.hulk or m.team == capturer.team or m.is_disabled() or not m.awake:
			continue
		if m.num_weapons == 0 or m.position.distance_to(t.position) > BLOCK_CAPTURE_M:
			continue
		if not near and not is_contact(capturer.team, m):
			continue
		return m
	return null


## Where to walk to capture: a mover's position, or for a building a reachable cell
## within capture reach of it (its own cell can be an island inside its footprint).
func _capture_goal(u: SimUnit, t: SimUnit) -> Vector2:
	if t.is_mover():
		return t.position
	var extent: float = (t as SimStructure).extent_m
	var tried := {}
	for r in [extent + 6.0, extent + 14.0, CAPTURE_M + extent - 2.0]:
		var ring := []
		for k in 16:
			var dir := Vector2.from_angle(TAU * k / 16.0)
			var p := world.map.nearest_walkable(t.position + dir * r, u.hover, 3)
			var c := world.map.cell_of(p)
			if tried.has(c) or p.distance_to(t.position) > CAPTURE_M + extent:
				continue
			tried[c] = true
			ring.append(p)
		ring.sort_custom(func(a, b): return a.distance_to(u.position) < b.distance_to(u.position))
		for p in ring:
			if world.map.cell_of(p) == world.map.cell_of(u.position) or world.map.find_path(u.position, p, u.hover).size() > 0:
				return p
	return t.position


## Each tick of a capture order; true when it's over (captured, already ours, or blocked).
func _capture_step(p: Pilot, u: SimUnit, o: Dictionary) -> bool:
	var t: SimUnit = o["target"]
	if t == null or t.team == u.team:
		return true
	if not can_capture(t, u.team):
		return true
	# The source measures to the target's centre; for big buildings (extent > 30 m) the
	# reachable cells lie further out, so allow the extent too (spec A2 ambiguity).
	var reach := CAPTURE_M + ((t as SimStructure).extent_m if t is SimStructure else 0.0)
	var arrived := u.position.distance_to(t.position) <= reach
	var blocker := capture_blocker(t, u, arrived)
	if blocker:
		world.order_hold(u)
		world.events.append({"type": "capture_blocked", "unit": u.id, "target": t.id, "by": blocker.id})
		return true
	if arrived:
		capture(u, t)
		world.order_hold(u)
		return true
	if t.is_mover() and (t.position.distance_to(o["goal"]) > 15.0 or u.order == SimWorld.Order.HOLD):
		o["goal"] = t.position  # follow a moving target (a convoy vehicle)
		world.order_move(u, o["goal"])
	return false


## The capture itself: a building changes hands; a vehicle becomes an inert hulk.
## A type with Resource Points pays them to the player (support-powers.md 1).
func capture(by: SimUnit, t: SimUnit) -> void:
	if by.team == sm.player_team and t.resource_points > 0 and sm.support:
		sm.support.rp += t.resource_points
		world.events.append({"type": "resource_points", "amount": t.resource_points, "unit": t.id})
	t.team = by.team
	if t is SimStructure:
		t.commander = by.commander
	else:
		t.hulk = true
		t.awake = false
		t.current_target = null
		world.order_hold(t)
		if t.brain is Pilot:
			t.brain.order = {"code": TO_NONE}
	world.events.append({"type": "captured", "unit": by.id, "target": t.id})


# --- objects and IDs (1) -----------------------------------------------------------------

func obj(id: int) -> SimUnit:
	if id == -1:
		return current.unit if current else null
	if id <= 0:
		return null
	var u: SimUnit = _by_part.get(id)
	return u if u != null and u.exists else null


## Members of a unit ID (squad match), team ID (500+) or a single object (1.4).
func members(id: int) -> Array:
	if id >= 500 and id <= 511:
		return world.units.filter(func(u): return u.is_mover() and u.exists and u.team == id - 500)
	if id >= 1 and id < 500:
		return world.units.filter(func(u): return u.is_mover() and u.squad == id)
	var o := obj(id)
	return [o] if o else []


func _group_mates(u: SimUnit) -> Array:
	if u.group < 0:
		return [u]
	return world.units.filter(func(o): return o.is_mover() and o.commander == u.commander and o.group == u.group)


static func status_of(u: SimUnit) -> int:
	match u.status:
		SimUnit.Status.DISABLED:
			return 1
		SimUnit.Status.DESTROYED:
			return 2
		SimUnit.Status.SHUTDOWN:
			return 5
	return 0


static func class_of(u: SimUnit) -> int:
	if u is SimMech:
		return 2
	if u is SimVehicle:
		return 3
	if u is SimStructure:
		return 16
	return 0


func wu(p: Vector2) -> Array:
	return [p.x / WU, p.y / WU, world.map.height_at(p) / WU]


static func m_of(a: Array) -> Vector2:
	return Vector2(float(a[0]), float(a[1])) * WU


func _armed(u: SimUnit) -> bool:
	for w in u.weapon_indices():
		if u.weapon_shots(w) != 0:
			return true
	return false


# --- contacts and scanning (2.6, 57) ------------------------------------------------------

func is_contact(team: int, m: SimUnit) -> bool:
	if not m.is_mover() or not m.exists or m.team == team:
		return false
	if sm.support and sm.support.probe_covers(team, m.position):
		return true  # sensor probe (support-powers.md 3.2)
	for f in world.units:
		if f.team == team and f.is_mover() and f.exists and f.awake and not f.is_disabled() \
				and f.position.distance_to(m.position) <= SENSOR_M:
			return true
	return false


func meets(viewer: SimUnit, m: SimUnit, criteria: int) -> bool:
	if not is_contact(viewer.team, m):
		return false
	if criteria & C_ENEMY and m.team == viewer.team:
		return false
	if criteria & C_NOT_DISABLED and m.is_disabled():
		return false
	if criteria & C_ARMED and not _armed(m):
		return false
	if criteria & C_NOT_CHALLENGED and m.brain is Pilot and m.brain.challenger != null:
		return false
	return true


## Walk the target priority list; returns the scan target or null.
func scan(p: Pilot) -> SimUnit:
	var me := p.unit
	for e in p.priorities:
		var type := int(e["type"])
		var p1 := int(e["p1"])
		var radius := float(e["p2"])
		var crit := int(e["p3"]) | (C_ARMED if type in [1, 2] else 0)  # the toggling ARMED bit, made steady
		match type:
			0:
				break
			1, 2:
				var cand: SimUnit = null
				if p1 > 0:
					cand = obj(p1)
				elif type == 2:
					var best := INF
					for m in world.units:
						if m.is_mover() and m.exists and meets(me, m, crit):
							var d := me.position.distance_to(m.position)
							if d < best:
								best = d
								cand = m
				if cand and me.position.distance_to(cand.position) < radius and (not cand.is_mover() or crit == 0 or meets(me, cand, crit)):
					p.last_scan = cand
					return cand
			3:
				var best_b := INF
				var pick: SimUnit = null
				for s in world.units:
					if s is SimStructure and s.exists and not s.is_destroyed() and s.team != me.team and s.team >= 0:
						var d := me.position.distance_to(s.position)
						if d < best_b:
							best_b = d
							pick = s
				if pick and best_b < radius:
					p.last_scan = pick
					return pick
			4:
				var t: SimUnit = p.order.get("target") if int(p.order["code"]) == TO_ATTACK_OBJECT else null
				if t and t.is_disabled() and not p.order.get("obliterate", false):
					t = null
				if t == null:
					t = me.current_target
				if t and not t.is_destroyed() and me.position.distance_to(t.position) < radius \
						and (int(e["p3"]) == 0 or not t.is_mover() or meets(me, t, int(e["p3"]))):
					p.last_scan = t
					return t
	p.last_scan = null
	return null


# --- natives --------------------------------------------------------------------------

func _register() -> void:
	var r := runtime
	r.register_native("setDebugString", func(_i, a):
		var o := obj(int(a[0]))
		if o and o.brain is Pilot and int(a[1]) >= 0 and int(a[1]) < 5:
			o.brain.debug[int(a[1])] = str(a[2])
		return 0)
	r.register_native("setDebugWindow", func(_i, a): return int(a[1]))
	r.register_native("getObjectPosition", func(_i, a):
		var o := obj(int(a[0]))
		var v := wu(o.position) if o else [0.0, 0.0, 0.0]
		for k in 3:
			a[1][k] = float(v[k])
		return 0)
	r.register_native("getTime", func(_i, _a): return world.time)
	r.register_native("getLogisticsTime", func(_i, _a): return _logistics_ms)
	r.register_native("getId", func(_i, _a): return current.unit.part_id if current else 0)
	r.register_native("objectClass", func(_i, a):
		var o := obj(int(a[0]))
		return class_of(o) if o else -1)
	r.register_native("objectTypeId", func(_i, a):
		var o := obj(int(a[0]))
		if o == null:
			return -1
		return (o as SimStructure).object_type if o is SimStructure else 0)
	r.register_native("objectStatus", func(_i, a):
		var id := int(a[0])
		if id >= 1 and id <= 511:
			for m in members(id):
				if not m.is_disabled():
					return 0
			return 1
		var o := obj(id)
		return status_of(o) if o else -1)
	r.register_native("objectStatusCount", func(_i, a):
		var id := int(a[0])
		var list := []
		if id >= 16 and id <= 31:
			list = world.units.filter(func(u): return u.is_mover() and u.commander == 0 and u.group == id - 16)
		elif id >= 165 and id <= 180:
			list = world.units.filter(func(u): return u.is_mover() and u.commander == 1 and u.group == id - 165)
		elif id >= 329 and id <= 344:
			list = world.units.filter(func(u): return u.is_mover() and u.commander == 2 and u.group == id - 329)
		elif id >= 500 or id == -1:
			list = members(id)
		for m in list:
			var slot := 8 if not m.exists else (7 if not m.awake else status_of(m))
			a[1][slot] = int(a[1][slot]) + 1
		return 0)
	r.register_native("objectSide", func(_i, a):
		var o := obj(int(a[0]))
		return (500 + o.team) if o else -1)
	r.register_native("objectTeam", func(_i, a):
		var o := obj(int(a[0]))
		return (500 + o.team) if o else -1)
	r.register_native("getObjectDamage", func(_i, a):
		var s := obj(int(a[0])) as SimStructure
		if s:
			return 100 if s.damage_level <= 0.0 else int(floor(s.damage / s.damage_level * 100.0))
		return 0)
	r.register_native("setObjectDamage", func(_i, a):
		var s := obj(int(a[0])) as SimStructure
		var pct := mini(int(a[1]), 100)
		if s and pct > 0:
			s.damage = maxf(s.damage, s.damage_level * pct / 100.0)
			if pct >= 100:
				s.status = SimUnit.Status.DESTROYED
		return 0)
	r.register_native("getObjectActive", func(_i, a):
		var n := 0
		for m in members(int(a[0])):
			if m.awake:
				n += 1
		return n)
	r.register_native("objectRemove", func(_i, a):
		var o := obj(int(a[0]))
		if o == null or not o.is_mover():
			return 1
		o.exists = false
		world.order_hold(o)
		return 0)
	r.register_native("distanceToObject", func(_i, a):
		var b := obj(int(a[1]))
		if b == null:
			return -1.0
		var best := -1.0
		for m in members(int(a[0])):
			if m.exists and m.awake:
				var d: float = m.position.distance_to(b.position)
				if best < 0.0 or d < best:
					best = d
		return best)
	r.register_native("distanceToPosition", func(_i, a):
		var goal := m_of(a[1])
		var best := -1.0
		for m in members(int(a[0])):
			if m.exists and m.awake:
				var d: float = m.position.distance_to(goal)
				if best < 0.0 or d < best:
					best = d
		return best)
	r.register_native("inArea", func(_i, a):
		var id := int(a[0])
		var centre := m_of(a[1])
		var radius := float(a[2])
		var min_in := int(a[3])
		var alive := func(m): return m.exists and m.awake and not m.is_disabled()
		if id > 511 or id == -1:
			if min_in == 0:
				return true
			var o := obj(id)
			return o != null and alive.call(o) and o.position.distance_to(centre) <= radius
		var list := members(id)
		if min_in == -1:
			var any := false
			for m in list:
				if alive.call(m):
					any = true
					if m.position.distance_to(centre) > radius:
						return false
			return any
		var n := 0
		for m in list:
			if alive.call(m) and m.position.distance_to(centre) <= radius:
				n += 1
		return n >= min_in)
	r.register_native("getUnitMates", func(_i, a):
		var id := int(a[0])
		var list := _group_mates(obj(id)) if id > 511 and obj(id) else members(id)
		for k in list.size():
			if k < a[1].size():
				a[1][k] = list[k].part_id
		return list.size())
	r.register_native("getRelativePositionToObject", func(_i, a):
		var o := obj(int(a[0]))
		if o == null:
			return 0
		var ang := float(a[1])
		var dist := float(a[2])
		var flags := int(a[3])
		var ours := (180.0 - ang) if flags & 1 else (o.facing + 180.0 - ang)
		var dir := Vector2(sin(deg_to_rad(ours)), cos(deg_to_rad(ours)))
		var goal := o.position + dir * dist
		var cell := world.map.cell_of(goal)
		var steps := 0
		while not world.map.is_walkable(cell, o.hover) and steps < 200:
			goal = goal.move_toward(o.position, world.map.cell_m * 0.5)
			cell = world.map.cell_of(goal)
			steps += 1
		var v := wu(goal)
		for k in 3:
			a[4][k] = float(v[k])
		return 0)
	r.register_native("convertCoords", func(_i, a):
		if int(a[0]) == 0:
			var c := world.map.cell_of(m_of(a[1]))
			a[2][0] = c.y
			a[2][1] = c.x
		else:
			var p := world.map.cell_center(Vector2i(int(a[2][1]), int(a[2][0])))
			a[1][0] = p.x / WU
			a[1][1] = p.y / WU
			a[1][2] = 0.0
		return 0)
	r.register_native("addTriggerArea", func(_i, a):
		var h := _next_area
		_next_area = mini(_next_area + 1, 15)
		trigger_areas[h] = {"r1": int(a[0]), "c1": int(a[1]), "r2": int(a[2]), "c2": int(a[3]),
			"type": int(a[4]), "param": int(a[5]), "hit": false}
		return h)
	r.register_native("isTriggerAreaHit", func(_i, a):
		return trigger_areas.get(int(a[0]), {}).get("hit", false))
	r.register_native("resetTriggerArea", func(_i, a):
		if trigger_areas.has(int(a[0])):
			trigger_areas[int(a[0])]["hit"] = false
		return 0)
	r.register_native("removeTriggerArea", func(_i, a):
		trigger_areas.erase(int(a[0]))
		return 0)
	# --- pilot (current warrior only; neutral outside a brain, 2.3) ---
	r.register_native("setTargetPriority", func(_i, a):
		if current == null:
			return 0
		var idx := clampi(int(a[0]), 0, 19)
		while current.priorities.size() <= idx:
			current.priorities.append({"type": 0, "p1": 0, "p2": 0, "p3": 0})
		current.priorities[idx] = {"type": int(a[1]), "p1": int(a[2]), "p2": float(a[3]), "p3": int(a[4])}
		current.priorities.resize(idx + 1)
		return 0)
	r.register_native("getNextPilotEvent", func(_i, a):
		if current == null:
			return -1
		var codes := current.history.keys()
		codes.sort()
		for c in codes:
			if c > current.cursor and not current.history[c].is_empty():
				current.cursor = c
				var list: Array = current.history[c]
				for k in list.size():
					if k < a[0].size():
						a[0][k] = list[k]
				return c
		return -1)
	r.register_native("getAlarmTriggers", func(_i, a):
		if current == null or current.alarm < 0:
			return 0
		var list: Array = current.history.get(current.alarm, [])
		for k in list.size():
			if k < a[0].size():
				a[0][k] = list[k]
		return list.size())
	r.register_native("getTarget", func(_i, a):
		var o := obj(int(a[0]))
		if o == null or not o.is_mover() or o.current_target == null or o.current_target.is_destroyed():
			return 0
		return o.current_target.part_id)
	r.register_native("setTarget", func(_i, a):
		var t := obj(int(a[1]))
		for m in members(int(a[0])):
			m.current_target = t
		return 0)
	r.register_native("getWeapons", func(_i, a):
		if current == null:
			return 0
		var u := current.unit
		var n := 0
		for w in u.weapon_indices():
			if int(a[1]) == 1 and u.weapon_shots(w) == 0:
				continue
			if n < a[0].size():
				a[0][n] = int(u.items[w].get("master_id", 0))
			n += 1
		return n)
	r.register_native("getWeaponRanges", func(_i, a):
		var o := obj(int(a[0]))
		var reach := world.attack_range(o) if o and o.is_mover() else 0.0
		a[1][0] = 0.0
		a[1][1] = reach * 0.6
		a[1][2] = reach
		return 0)
	r.register_native("getFireRanges", func(_i, a):
		for k in 4:
			a[0][k] = [60.0, 120.0, 180.0, 250.0][k]
		return 0)
	r.register_native("setIntegerMemory", func(_i, a):
		if current and int(a[0]) >= 0 and int(a[0]) < 60:
			current.cells[int(a[0])] = int(a[1])
		return 0)
	r.register_native("setRealMemory", func(_i, a):
		if current and int(a[0]) >= 0 and int(a[0]) < 60:
			current.cells[int(a[0])] = float(a[1])
		return 0)
	r.register_native("getIntegerMemory", func(_i, a):
		return int(current.cells[int(a[0])]) if current and int(a[0]) >= 0 and int(a[0]) < 60 else 0)
	r.register_native("getRealMemory", func(_i, a):
		return float(current.cells[int(a[0])]) if current and int(a[0]) >= 0 and int(a[0]) < 60 else 0.0)
	r.register_native("setWillHelp", func(_i, a):
		if current == null:
			return false
		var was := current.will_help
		current.will_help = AblRuntime._truthy(a[0])
		return was)
	r.register_native("setEject", func(_i, _a): return false)
	r.register_native("setMoveArea", func(_i, a):
		if current:
			current.move_area = {} if float(a[1]) <= 0.0 else {"centre": m_of(a[0]), "radius": float(a[1])}
		return 0)
	r.register_native("getChallenger", func(_i, a):
		var o := obj(int(a[0]))
		return o.brain.challenger.part_id if o and o.brain is Pilot and o.brain.challenger else 0)
	r.register_native("setChallenger", func(_i, a):
		var v := obj(int(a[0]))
		if v == null or not (v.brain is Pilot):
			return -2
		v.brain.challenger = obj(int(a[1]))
		return 0)
	r.register_native("requestHelp", func(_i, a):
		_request_help(int(a[0]), m_of(a[1]), float(a[2]), m_of(a[3]), float(a[4]), int(a[5]))
		return 0.0)
	r.register_native("requestTarget", func(_i, a):
		if current == null:
			return 0
		var centre := m_of(a[0])
		var best: SimUnit = null
		var best_d := INF
		for m in world.enemies_of(current.unit):
			var d := m.position.distance_to(centre)
			if d <= float(a[1]) and _armed(m) and d < best_d:
				best = m
				best_d = d
		return best.part_id if best else 0)
	r.register_native("requestShelter", func(_i, a):
		if current == null:
			return 0
		var near := []
		for s in world.units:
			if s is SimStructure and s.exists and current.unit.position.distance_to(s.position) <= float(a[0]):
				near.append(s)
				if near.size() >= 10:
					break
		return near[runtime.rng.randi_range(0, near.size() - 1)].part_id if not near.is_empty() else 0)
	r.register_native("getCurrentBRValue", func(_i, a):
		var o := obj(int(a[0]))
		return int(o.tonnage) if o else -1)
	r.register_native("getUnitStatus", func(_i, a):
		var o := obj(int(a[0]))
		if o == null or o.is_disabled():
			return 0.0
		if o is SimStructure:
			var s := o as SimStructure
			if is_inf(s.damage_level):
				return 100.0
			return 100.0 * maxf(s.damage_level - s.damage, 0.0) / maxf(s.damage_level, 1.0)
		var tot := 0.0
		var cur := 0.0
		for k in o.armor.size():
			tot += o.max_armor[k]
			cur += o.armor[k]
		return 100.0 * cur / maxf(tot, 1.0))
	r.register_native("setPilotState", func(inst, a):
		var prev: int = inst.state_handle() if inst else 0
		var h := int(a[0])
		if inst and h > 0 and h <= inst.unit["states"].size():
			runtime._trans(inst, inst.unit["states"][h - 1])
		return prev)
	r.register_native("getTacOrder", func(_i, a):
		var o := obj(int(a[0]))
		if o == null or not (o.brain is Pilot):
			return 0
		var ord: Dictionary = o.brain.order
		var params: Array = a[2]
		params[0] = int(ord["code"])
		params[1] = int(ord.get("origin", 2))
		var t: SimUnit = ord.get("target")
		params[3] = t.part_id if t else 0
		params[4] = class_of(t) if t else 0
		params[5] = 0
		if params.size() > 18:
			match int(ord["code"]):
				TO_MOVETO_POINT:
					var g: Vector2 = ord["goal"]
					params[7] = 1 if ord.get("run", false) else 0
					params[9] = int(g.x / WU)
					params[10] = int(g.y / WU)
				TO_ATTACK_OBJECT:
					params[13] = 1 if ord.get("pursue", false) else 0
					params[14] = 1 if ord.get("obliterate", false) else 0
			params[17] = 0
			params[18] = 0
		return int(ord["code"]))
	r.register_native("clearTacOrder", func(_i, _a):
		if current:
			current.order = {"code": TO_NONE}
			world.order_hold(current.unit)
		return 0)
	# --- contacts (57) ---
	r.register_native("getContacts", func(_i, a):
		if current == null:
			return 0
		var list := []
		for m in world.units:
			if m.is_mover() and m.exists and meets(current.unit, m, int(a[1])):
				list.append(m)
		if int(a[2]) == 2:
			var me := current.unit
			list.sort_custom(func(x, y): return me.position.distance_to(x.position) < me.position.distance_to(y.position))
		for k in list.size():
			if k < a[0].size():
				a[0][k] = list[k].part_id
		return list.size())
	r.register_native("selectContact", func(_i, a):
		if current == null:
			return -1
		var o := obj(int(a[1]))
		if o and is_contact(current.unit.team, o):
			current.set_meta("contact", o)
			return 0
		return 1)
	r.register_native("getContactId", func(_i, _a):
		var c = current.get_meta("contact", null) if current else null
		return c.part_id if c else 0)
	r.register_native("getContactRelativePosition", func(_i, a):
		var c = current.get_meta("contact", null) if current else null
		if c == null:
			return 1
		return 0)
	r.register_native("getLastScan", func(_i, _a):
		return current.last_scan.part_id if current and current.last_scan else 0)
	r.register_native("getSensorsActive", func(_i, _a):
		for m in world.units:
			if m.team != sm.player_team and is_contact(sm.player_team, m) and not m.is_disabled():
				return true
		return false)
	r.register_native("getPlayerInCombat", func(_i, _a):
		for m in world.units:
			if m.team == sm.player_team and m.is_mover() and not m.is_disabled() and m.current_target != null:
				return true
		return false)
	# --- order-flagged core natives (2.7) ---
	for alias in [["coreAttack", "newAttack"], ["coreMoveTo", "newMoveTo"], ["coreMoveToObject", "newMoveToObject"],
			["corePower", "newPower"], ["newScan", "coreScan"], ["coreEject"]]:
		var fn: Callable = {"coreattack": _n_core_attack, "coremoveto": _n_core_move, "coremovetoobject": _n_core_move_object,
			"corepower": _n_core_power, "newscan": _n_new_scan, "coreeject": _n_core_eject}[alias[0].to_lower()]
		for n in alias:
			r.register_native(n, fn, true)
	# --- old-style order natives (plain functions; 0 = issued, 1 = done) ---
	r.register_native("orderMoveTo", func(_i, a):
		if current == null:
			return 1
		var goal := m_of(a[0])
		if world.map.cell_of(current.unit.position) == world.map.cell_of(goal):
			return 1
		_issue(current, {"code": TO_MOVETO_POINT, "goal": goal, "run": AblRuntime._truthy(a[1]), "origin": 1})
		return 0)
	r.register_native("orderMoveToObject", func(_i, a):
		var o := obj(int(a[0]))
		if current == null or o == null or int(a[0]) < 512:
			return 1
		if world.map.cell_of(current.unit.position) == world.map.cell_of(o.position):
			return 1
		_issue(current, {"code": TO_MOVETO_OBJECT, "goal": o.position, "origin": 1})
		return 0)
	r.register_native("orderAttackObject", func(_i, a):
		var o := obj(int(a[0]))
		if current == null or (int(a[0]) >= 1 and int(a[0]) <= 511):
			return 1
		if o == null:
			if int(current.order["code"]) == TO_ATTACK_OBJECT:
				current.order = {"code": TO_NONE}
			return 1
		if current.unit.num_weapons == 0 or o.is_destroyed():
			return 1
		_issue(current, {"code": TO_ATTACK_OBJECT, "target": o, "pursue": AblRuntime._truthy(a[4]), "origin": 1})
		return 0)
	r.register_native("orderWait", func(_i, a):
		if current == null:
			return 1
		if AblRuntime._truthy(a[1]):
			current.unit.current_target = null
		_issue(current, {"code": TO_WAIT, "end": world.time + float(int(a[0])), "origin": 1})
		return 1 if int(a[0]) <= 0 else 0)
	r.register_native("orderWithdraw", func(_i, _a): return 0)
	# --- mission / objectives ---
	r.register_native("checkObjectiveStatus", func(_i, a):
		var n := int(a[0])
		var objs: Array = sm.objectives.objectives
		if n < 0 or n >= objs.size():
			return 0
		return 1 if objs[n]["complete"] else (2 if objs[n].get("failed", false) else 0))
	r.register_native("getMissionWon", func(_i, _a): return script_result >= 4 or sm.objectives.result == SimObjectives.Result.WON)
	r.register_native("getMissionLost", func(_i, _a): return script_result in [1, 2] or sm.objectives.result == SimObjectives.Result.LOST)
	r.register_native("getMissionStatus", func(_i, _a): return 0 if sm.objectives.pending_result == SimObjectives.Result.PLAYING else script_result)
	r.register_native("getGeneralAlarm", func(_i, _a): return 0)
	r.register_native("setInvulnerable", func(_i, a):
		sm.player_invulnerable = AblRuntime._truthy(a[0])
		return 0)
	r.register_native("objectChangeSides", func(_i, _a): return 0)  # a no-op in the original (spec A6)
	r.register_native("isCaptured", func(_i, a):
		var n := 0
		for m in members(int(a[0])):
			if m.captured_flag:
				n += 1
		return n)
	r.register_native("setCaptured", func(_i, a):
		var o := obj(int(a[0]))
		if o:
			o.captured_flag = true
		return 0)
	r.register_native("setCapturable", func(_i, a):
		var o := obj(int(a[0]))
		if o:
			o.capturable = true  # the bool argument is ignored in the original
		return 0)
	r.register_native("wasEverCapturable", func(_i, a):
		var o := obj(int(a[0]))
		return o != null and o.capturable)
	r.register_native("isCapturable", func(_i, a):
		var o := obj(int(a[0]))
		var team := int(a[1])
		if o == null:
			return false
		if team == -2:
			return o.capturable and not o.is_destroyed()
		return can_capture(o, team - 500 if team >= 500 else team))
	r.register_native("isTeamCapturing", func(_i, a):
		var team := int(a[0])
		var t := obj(int(a[1]))
		for p in pilots:
			if int(p.order["code"]) == TO_CAPTURE and p.order.get("target") == t and (team == 0 or 500 + p.unit.team == team):
				return true
		return false)
	r.register_native("isTeamTargeting", func(_i, a):
		var team := int(a[0])
		var t := obj(int(a[1]))
		for m in world.units:
			if m.is_mover() and m.current_target == t and t != null and (team == 0 or 500 + m.team == team) and m.part_id != int(a[2]):
				return true
		return false)
	r.register_native("setRevealed", func(_i, _a): return 0)
	r.register_native("callStrikeEx", func(_i, _a): return 0)
	r.register_native("orderDeployElementals", func(_i, _a): return 0)
	r.register_native("getFixed", func(_i, _a): return -1)
	# --- presentation (P): events for the view ---
	r.register_native("playDigitalMusic", func(_i, a):
		# mc2_01.abl re-requests its sensor tune every frame; the music system ignores repeats.
		if int(a[0]) != music_id:
			music_id = int(a[0])
			world.events.append({"type": "abl_music", "id": music_id})
		return 0)
	r.register_native("getCurrentMusicId", func(_i, _a): return music_id)
	r.register_native("playWave", func(_i, a):
		world.events.append({"type": "abl_wave", "file": str(a[0])})
		return 0)
	r.register_native("playSoundEffect", func(_i, a):
		world.events.append({"type": "abl_sfx", "id": int(a[0])})
		return 0)
	r.register_native("playSpeech", func(_i, _a): return 0)
	r.register_native("playVideo", func(_i, a):
		world.events.append({"type": "abl_video", "file": str(a[0])})
		return 0)
	r.register_native("isPlayingVoiceOver", func(_i, _a): return voice_busy.call() if voice_busy.is_valid() else false)
	r.register_native("stopVoiceOver", func(_i, _a): return 0)
	r.register_native("inCallout", func(_i, _a): return false)
	r.register_native("forceMovieEnd", func(_i, _a): return 0)
	for name in ["setMovieMode", "endMovieMode"]:
		var n: String = name
		r.register_native(n, func(_i, _a):
			world.events.append({"type": "abl_" + n.to_lower()})
			return 0)
	for name in ["setCameraPosition", "setCameraRotation", "setCameraGoalPosition", "setCameraGoalRotation", "fadeToColor"]:
		var n2: String = name
		r.register_native(n2, func(_i, a):
			world.events.append({"type": "abl_camera", "call": n2.to_lower(), "args": a.duplicate(true)})
			return 0)
	for name in ["getCameraPosition", "getCameraRotation"]:
		r.register_native(name, func(_i, _a): return 0)


# --- core orders --------------------------------------------------------------------------

func _n_core_attack(_i, a: Array) -> int:
	return _core_attack(int(a[0]), int(a[1]))


func _n_core_move(_i, a: Array) -> int:
	return _core_move(m_of(a[0]), int(a[1]))


func _n_core_move_object(_i, a: Array) -> int:
	return _core_move_object(int(a[0]), int(a[1]))


func _n_core_power(_i, a: Array) -> int:
	return _core_power(AblRuntime._truthy(a[0]))


func _n_core_eject(_i, _a: Array) -> int:
	return _core_eject()


func _n_new_scan(_i, a: Array) -> int:
	return _new_scan(int(a[0]), int(a[1]))


func _core_attack(target_id: int, params: int) -> int:
	if current == null:
		return 1
	var u := current.unit
	if u.num_weapons == 0:
		return 1
	var t: SimUnit = null
	if target_id == 0:
		t = current.last_scan if current.last_scan else scan(current)
	else:
		t = obj(target_id)
	if t == null or t.is_destroyed() or (t.is_disabled() and not (params & P_OBLITERATE)):
		return 1
	var pursue := (params & P_PURSUE) != 0 or (params & P_STOP_AND_FIRE) != 0
	if params & P_TURRET:
		pursue = false
	var o := {"code": TO_ATTACK_OBJECT, "target": t, "pursue": pursue, "obliterate": (params & P_OBLITERATE) != 0, "origin": 2}
	if _same_order(current, o):
		return 0
	_issue(current, o)
	return 0


func _core_move(goal: Vector2, params: int) -> int:
	if current == null:
		return 1
	var u := current.unit
	if world.map.cell_of(u.position) == world.map.cell_of(goal):
		return 1
	var o := {"code": TO_MOVETO_POINT, "goal": goal, "run": (params & P_RUN) != 0, "origin": 2}
	if _same_order(current, o):
		return 0
	if params & P_DONT_SET_ORDER:
		world.order_move(u, goal)
		return 0
	_issue(current, o)
	return 0


func _core_move_object(id: int, params: int) -> int:
	if current == null:
		return 1
	var t: SimUnit = (current.last_scan if current.last_scan else scan(current)) if id == 0 else obj(id)
	if t == null:
		return 1
	var goal := t.position if t.is_mover() else world.map.nearest_walkable(t.position + (current.unit.position - t.position).normalized() * ((t as SimStructure).extent_m if t is SimStructure else 5.0))
	if world.map.cell_of(current.unit.position) == world.map.cell_of(goal):
		return 1
	var o := {"code": TO_MOVETO_OBJECT, "goal": goal, "run": (params & P_RUN) != 0, "origin": 2}
	if _same_order(current, o):
		return 0
	_issue(current, o)
	return 0


func _core_power(up: bool) -> int:
	if current == null:
		return 1
	var u := current.unit
	if not (u is SimMech) or u.is_disabled():
		return 1
	if up:
		if u.status == SimUnit.Status.NORMAL and not u.powered_down:
			return 1
		u.powered_down = false
		u.status = SimUnit.Status.NORMAL
		current.order = {"code": TO_POWERUP, "origin": 2}
		return 0
	if u.status == SimUnit.Status.SHUTDOWN:
		return 1
	world.order_hold(u)
	u.current_target = null
	u.powered_down = true
	u.status = SimUnit.Status.SHUTDOWN
	current.order = {"code": TO_POWERDOWN, "origin": 2}
	return 0


func _core_eject() -> int:
	if current == null:
		return 1
	var u := current.unit
	if not (u is SimMech) or u.is_disabled():
		return 1
	if int(current.order["code"]) == TO_EJECT:
		return 0
	world.order_hold(u)
	u.ejected = true
	u.status = SimUnit.Status.DISABLED
	current.order = {"code": TO_EJECT, "origin": 2}
	return 1


func _new_scan(id: int, criteria: int) -> int:
	if current == null:
		return 0
	if id != 0:
		var o := obj(id)
		if o and (not o.is_mover() or meets(current.unit, o, criteria)):
			current.last_scan = o
			return o.part_id
		return 0
	var t := scan(current)
	return t.part_id if t else 0


## requestHelp (11): assign helpers near friendCentre to the enemy team's members near
## enemyCentre. Threat rating is approximated by tonnage.
func _request_help(enemy_id: int, friend_c: Vector2, friend_r: float, enemy_c: Vector2, enemy_r: float, priority: int) -> void:
	if current == null:
		return
	var me := current.unit
	var enemy := obj(enemy_id)
	if enemy == null or not enemy.is_mover() or enemy.team == me.team:
		return
	var helpers := []
	for m in world.units:
		if m.is_mover() and m.exists and not m.is_disabled() and m.team == me.team and m.commander == me.commander \
				and m.brain is Pilot and m.brain.will_help and m.num_weapons > 0 \
				and m.position.distance_to(friend_c) <= friend_r:
			if priority <= 0 and int(m.brain.order["code"]) != TO_NONE:
				continue
			helpers.append(m)
	var targets := []
	for m in world.units:
		if m.is_mover() and m.exists and not m.is_disabled() and m.team == enemy.team and m.position.distance_to(enemy_c) <= enemy_r:
			targets.append(m)
	if targets.is_empty():
		return
	helpers.sort_custom(func(x, y): return x.tonnage > y.tonnage)
	targets.sort_custom(func(x, y): return x.tonnage > y.tonnage)
	var load := {}
	for t in targets:
		load[t] = 0.0
	for h in helpers:
		var best: SimUnit = null
		var best_ratio := INF
		for t in targets:
			var ratio: float = load[t] / maxf(t.tonnage, 1.0)
			if ratio < best_ratio:
				best_ratio = ratio
				best = t
		load[best] += h.tonnage
		h.brain.raise(EV_ATTACK_ORDER, best.part_id)
