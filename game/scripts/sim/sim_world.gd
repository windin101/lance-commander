class_name SimWorld
extends RefCounted
## The running mission: units (mechs, vehicles, structures), orders, movement,
## AI brains, combat cadence, projectiles.
## Fixed 10 Hz tick; the view interpolates between ticks. Headless and seeded.
##
## Cadence follows the original's MechWarrior update frequencies
## (warrior.cpp:215): combat decisions every 0.25 s.

const TICK := 0.1
const COMBAT_PERIOD := 0.25
const ARRIVE_M := 3.0
const GETUP_TIME := 4.0
## Jump flight time. The original flies the mech from the Jump gesture's takeoff frame to
## its landing frame at 30 fps (mech3d.cpp:3968-3990), per appearance; those frames are not
## converted, so one flight time for all.
const JUMP_TIME := 2.0
const JUMP_APEX := 0.25  # arc height as a share of the jump distance (the view's arc only)
## pbrain's guard radii (pbrain.abl KludgeHandleGuard: SetEngageRadius(250),
## SetDisengageRadius(275)), used by the native guard of units without a pbrain.
const GUARD_ENGAGE_M := 250.0
const GUARD_DISENGAGE_M := 275.0

## HOLD also serves the original's TACTICAL_ORDER_STOP and WAIT. JUMP = JUMPTO_POINT,
## GUARD = TACTICAL_ORDER_GUARD (point or object). New values go last (saves, tests).
enum Order { HOLD, MOVE, ATTACK, JUMP, GUARD }

var rules: SimRules
var map: SimMap
var rng: SimRng
var time := 0.0
var units: Array[SimUnit] = []
var projectiles: Array[Dictionary] = []  # {shot, target_id, impact_time}
var events: Array[Dictionary] = []  # drained by the view each frame
var flags: Dictionary = {}  # mission boolean flags (objectives, mission script, brains)
var movie_mode := false  # a mission cinematic runs (ABL setMovieMode): no player orders until endMovieMode
var fire_discipline_level := 20  # don't fire a weapon that would push heat past this level
var projectile_speed := {"EnergyWeapon": 0.0, "BallisticWeapon": 450.0, "MissileWeapon": 160.0, "Weapon": 450.0}

var _combat_clock := 0.0


func _init(sim_rules: SimRules, sim_map: SimMap, seed_value: int = 1) -> void:
	rules = sim_rules
	map = sim_map
	rng = SimRng.new(seed_value)


func add_unit(u: SimUnit) -> SimUnit:
	u.id = units.size()
	u.order = Order.HOLD
	u.prev_position = u.position
	u.prev_facing = u.facing
	units.append(u)
	return u


## Hostile units that can be auto-targeted (movers only; structures need an order).
func enemies_of(m: SimUnit) -> Array[SimUnit]:
	var out: Array[SimUnit] = []
	for o in units:
		if o.team != m.team and o.is_mover() and o.exists and not o.is_disabled():
			out.append(o)
	return out


func unit_by_part(part_index: int) -> SimUnit:
	for u in units:
		if u.part_index == part_index:
			return u
	return null


# --- orders -----------------------------------------------------------------

## run: TRAVEL_MODE_FAST (run speed) or SLOW (walk speed); the order's mode picks the
## gesture (warrior.cpp:3302 setMoveRun, mech.cpp:4197 allowedToRun).
func order_move(m: SimUnit, goal: Vector2, run := true) -> bool:
	if _after_landing(m, func(): order_move(m, goal, run)):
		return true
	var path := map.find_path(m.position, map.nearest_walkable(goal, m.hover), m.hover)
	m.order = Order.MOVE
	m.order_target = null
	m.move_run = run
	m.path = path
	m.path_index = 0
	return path.size() > 0


## pursue false = fire from the current position (attackParams.pursue, missiongui.cpp:1806-1880):
## the unit turns to the target and fires when it is in range, but never moves to close.
func order_attack(m: SimUnit, target: SimUnit, run := true, pursue := true) -> void:
	if _after_landing(m, func(): order_attack(m, target, run, pursue)):
		return
	m.order = Order.ATTACK
	m.order_target = target
	m.move_run = run
	m.attack_pursue = pursue
	m.path = PackedVector2Array()
	m.repath_time = 0.0


func order_hold(m: SimUnit) -> void:
	if _after_landing(m, Callable()):
		return  # a jump always lands; it then stands
	m.order = Order.HOLD
	m.order_target = null
	m.path = PackedVector2Array()


## TACTICAL_ORDER_STOP (MechWarrior::orderStop, warrior.cpp:5908): no move goal, no attack
## target, no last target.
func order_stop(m: SimUnit) -> void:
	order_hold(m)
	m.current_target = null


## Why a jump to goal would be refused, or "" if it can be made: jump jets (canJump), the
## horizontal distance within getJumpRange and a passable landing cell (canJumpToWPos,
## missiongui.cpp:3492; Mover::handleTacticalOrder, mover.cpp:3186-3201).
func jump_refusal(m: SimUnit, goal: Vector2) -> String:
	if not m.can_jump():
		return "no_jump_jets"
	if m.is_disabled() or m.status != SimUnit.Status.NORMAL or (m is SimMech and (m.fallen or _legs_gone(m))):
		return "cannot_move"
	if m.position.distance_to(goal) > m.jump_range():
		return "out_of_range"
	var c := map.cell_of(goal)
	if not map.in_bounds(c) or not map.is_walkable(c, m.hover):
		return "impassable"
	return ""


## TACTICAL_ORDER_JUMPTO_POINT: fly straight to goal over anything in between
## (Mech3DAppearance jumpVelocity, mech3d.cpp:3984); refused (false) as the original refuses it.
func order_jump(m: SimUnit, goal: Vector2) -> bool:
	if m.order == Order.JUMP or jump_refusal(m, goal) != "":
		return false
	m.order = Order.JUMP
	m.order_target = null
	m.path = PackedVector2Array()
	m.jump_from = m.position
	m.jump_to = goal
	m.jump_start = time
	m.after_jump = Callable()
	events.append({"type": "jump", "unit": m.id, "to": goal})
	return true


## TACTICAL_ORDER_GUARD on a point (target null) or an object. Units with a pbrain get the
## original's guard from the brain (pbrain.abl Sentry / Guard, orders.abi:1387-1528); this is
## the same rule for units without one: stay at the anchor, engage an enemy that comes within
## GUARD_ENGAGE_M of it, chase it no further than GUARD_DISENGAGE_M from it, then return.
func order_guard(m: SimUnit, point: Vector2, target: SimUnit = null, run := true) -> void:
	if _after_landing(m, func(): order_guard(m, point, target, run)):
		return
	m.order = Order.GUARD
	m.order_target = null
	m.guard_point = point
	m.guard_target = target
	m.move_run = run
	m.attack_pursue = true
	m.path = PackedVector2Array()
	m.repath_time = 0.0


## An order given in the air takes effect on landing (the latest one wins); true if deferred.
func _after_landing(m: SimUnit, then: Callable) -> bool:
	if m.order != Order.JUMP:
		return false
	m.after_jump = then
	return true


func guard_anchor(m: SimUnit) -> Vector2:
	if m.guard_target and m.guard_target.exists:
		return m.guard_target.position
	return m.guard_point


# --- tick ---------------------------------------------------------------------

func step(dt: float = TICK) -> void:
	time += dt
	for m in units:
		m.prev_position = m.position
		m.prev_facing = m.facing
		m.prev_jump_alt = m.jump_alt
		if not m.exists:
			continue
		if m.brain and not m.is_disabled():
			m.brain.think(self, m)
		if m.is_mover():
			_update_motion(m, dt)
		if m.uses_heat:
			SimHeat.update(rules, rng, m, dt, time)
	_combat_clock += dt
	if _combat_clock >= COMBAT_PERIOD - 0.0001:
		_combat_clock -= COMBAT_PERIOD
		for m in units:
			_combat(m)
	_land_projectiles()
	for m in units:
		if m.is_disabled() and not m.reported_disabled:
			m.reported_disabled = true
			events.append({"type": "disabled", "unit": m.id, "destroyed": m.is_destroyed()})
			if m is SimVehicle and m.explosion_damage > 0.0:
				_splash(m)


## Vehicle death explosion: full ExplosionDamage to every mover within the radius,
## at an artillery-style hit location (gvehicl.cpp update, objmgr.cpp:2661).
func _splash(v: SimVehicle) -> void:
	for u in units:
		if u == v or not u.is_mover() or u.is_destroyed():
			continue
		if u.distance_to(v.position) > v.explosion_radius_m:
			continue
		var loc: int
		if u is SimMech:
			loc = SimCombat.hit_location(rules, rng, u, v.position)
		else:
			loc = u.roll_hit_location(rules, rng, v.position)
		SimCombat.apply_shot(rules, rng, u, {"hit": true, "damage": v.explosion_damage, "location": loc, "master_id": -3}, time)


func _update_motion(m: SimUnit, dt: float) -> void:
	m.speed = 0.0
	if m.order == Order.JUMP:  # airborne: always lands, whatever happens to it in flight
		_update_jump(m, dt)
		return
	if m.is_disabled() or m.status == SimUnit.Status.SHUTDOWN:
		m.body_state = SimUnit.BodyState.STANDING if not m.is_disabled() else m.body_state
		return
	if m is SimMech and m.fallen:
		if m.fall_time < 0.0:
			m.fall_time = time
			m.body_state = SimMech.BodyState.FALLEN_FORWARD
			events.append({"type": "fell", "unit": m.id})
		elif time - m.fall_time >= GETUP_TIME and not _legs_gone(m):
			m.fallen = false
			m.failed_piloting_check = false
			m.fall_time = -1.0
			m.body_state = SimMech.BodyState.STANDING
		return
	var goal = _current_goal(m)
	if goal != null and m.hold_position and m.order != Order.MOVE:
		# Hold position: only a move order moves the unit (warrior.cpp:3982-3988).
		goal = null
	if goal == null:
		m.body_state = SimMech.BodyState.STANDING
		_face_target(m, dt)
		return
	var to_goal: Vector2 = goal - m.position
	var dist := to_goal.length()
	var desired := rad_to_deg(atan2(to_goal.x, to_goal.y))  # 0 = north, clockwise
	var diff := wrapf(desired - m.facing, -180.0, 180.0)
	var max_turn := m.turn_rate * dt
	m.facing = wrapf(m.facing + clampf(diff, -max_turn, max_turn), 0.0, 360.0)
	var top := max_speed(m)
	var align := clampf(1.0 - (absf(diff) - 30.0) / 60.0, 0.0, 1.0)  # slow when turning hard
	m.speed = minf(top * align, dist / dt)
	m.position += Vector2(sin(deg_to_rad(m.facing)), cos(deg_to_rad(m.facing))) * m.speed * dt
	if m.speed <= 0.01:
		m.body_state = SimMech.BodyState.STANDING
	elif m is SimMech and _one_leg_gone(m):
		m.body_state = SimMech.BodyState.LIMPING
	elif m.speed > m.walk_speed + 0.5:
		m.body_state = SimMech.BodyState.RUNNING
	else:
		m.body_state = SimMech.BodyState.WALKING


## Airborne: straight line at constant speed, turning toward the landing point; lands on
## the goal and stands (the jump order is done).
func _update_jump(m: SimUnit, dt: float) -> void:
	var t := clampf((time - m.jump_start) / JUMP_TIME, 0.0, 1.0)
	var span := m.jump_to - m.jump_from
	m.position = m.jump_from + span * t
	m.speed = span.length() / JUMP_TIME
	m.jump_alt = 4.0 * JUMP_APEX * span.length() * t * (1.0 - t)
	m.body_state = SimUnit.BodyState.JUMPING
	if span.length() > 0.5:
		var diff := wrapf(rad_to_deg(atan2(span.x, span.y)) - m.facing, -180.0, 180.0)
		m.facing = wrapf(m.facing + clampf(diff, -m.turn_rate * dt, m.turn_rate * dt), 0.0, 360.0)
	if t >= 1.0:
		m.jump_alt = 0.0
		m.speed = 0.0
		m.body_state = SimUnit.BodyState.STANDING
		m.order = Order.HOLD
		m.path = PackedVector2Array()
		events.append({"type": "landed", "unit": m.id})
		var then := m.after_jump
		m.after_jump = Callable()
		if then.is_valid() and not m.is_disabled():
			then.call()


## Standing with a target outside the fire arc: turn in place toward it.
func _face_target(m: SimUnit, dt: float) -> void:
	var t: SimUnit = m.order_target if m.order in [Order.ATTACK, Order.GUARD] and m.order_target else m.current_target
	if t == null or t.is_disabled():
		return
	var rel := m.rel_facing_to(t.position)
	if absf(rel) <= fire_arc(m) - 10.0:
		return
	var max_turn := m.turn_rate * dt
	m.facing = wrapf(m.facing + clampf(rel, -max_turn, max_turn), 0.0, 360.0)


func fire_arc(m: SimUnit) -> float:
	return minf(float(m.max_torso_yaw) + m.fire_arc_half, 180.0)


## Next point to walk to, or null. Advances the path; handles attack approach.
func _current_goal(m: SimUnit) -> Variant:
	if m.order == Order.GUARD:
		return _guard_goal(m)
	if m.order == Order.ATTACK:
		var t: SimUnit = m.order_target
		if t == null or t.is_disabled():
			order_hold(m)
			return null
		if not m.attack_pursue or m.distance_to(t.position) <= attack_range(m):
			m.path = PackedVector2Array()
			return null
		if m.path.is_empty() or time >= m.repath_time:
			m.path = map.find_path(m.position, map.nearest_walkable(t.position, m.hover), m.hover)
			if m.path.is_empty():
				m.path = _firing_position_path(m, t)
			m.path_index = 0
			m.repath_time = time + 2.0
	if m.path.is_empty():
		if m.order == Order.MOVE:
			order_hold(m)
		return null
	while m.path_index < m.path.size() and m.position.distance_to(m.path[m.path_index]) < ARRIVE_M:
		m.path_index += 1
	if m.path_index >= m.path.size():
		m.path = PackedVector2Array()
		if m.order == Order.MOVE:
			order_hold(m)
		return null
	return m.path[m.path_index]


## Guard: pick up (or keep) an enemy near the anchor and close on it, else walk back.
func _guard_goal(m: SimUnit) -> Variant:
	if m.guard_target and (not m.guard_target.exists or m.guard_target.is_destroyed()):
		order_hold(m)  # Guard(): the guarded object is gone (FAILED)
		return null
	var anchor := guard_anchor(m)
	var t: SimUnit = m.order_target
	if t and (t.is_disabled() or not t.exists or t.position.distance_to(anchor) > GUARD_DISENGAGE_M):
		t = null
	if t == null:
		var best_d := GUARD_ENGAGE_M
		for e in enemies_of(m):
			var d := e.position.distance_to(anchor)
			if d <= best_d and (e.num_weapons > 0 or not m.is_player):
				best_d = d
				t = e
	m.order_target = t
	if t:
		if m.distance_to(t.position) <= attack_range(m):
			m.path = PackedVector2Array()
			return null
		if m.path.is_empty() or time >= m.repath_time:
			m.path = map.find_path(m.position, map.nearest_walkable(t.position, m.hover), m.hover)
			m.path_index = 0
			m.repath_time = time + 2.0
	elif m.position.distance_to(anchor) > ARRIVE_M * 4.0:
		if m.path.is_empty() or time >= m.repath_time:
			m.path = map.find_path(m.position, map.nearest_walkable(anchor, m.hover), m.hover)
			m.path_index = 0
			m.repath_time = time + 2.0
	else:
		m.path = PackedVector2Array()
		return null
	while m.path_index < m.path.size() and m.position.distance_to(m.path[m.path_index]) < ARRIVE_M:
		m.path_index += 1
	if m.path_index >= m.path.size():
		m.path = PackedVector2Array()
		return null
	return m.path[m.path_index]


## A target with no path to its cell (an island past deep water, a walled pocket): walk
## to a reachable cell within weapon range of it instead, nearest the attacker first.
func _firing_position_path(m: SimUnit, t: SimUnit) -> PackedVector2Array:
	var reach := attack_range(m) * 0.85
	for frac in [0.5, 0.75, 1.0]:
		var ring := []
		for k in 16:
			var p: Vector2 = t.position + Vector2.from_angle(TAU * k / 16.0) * reach * frac
			if map.in_bounds(map.cell_of(p)) and map.is_walkable(map.cell_of(p), m.hover):
				ring.append(p)
		ring.sort_custom(func(a, b): return a.distance_to(m.position) < b.distance_to(m.position))
		for p in ring:
			var path := map.find_path(m.position, p, m.hover)
			if not path.is_empty():
				return path
	return PackedVector2Array()


func max_speed(m: SimUnit) -> float:
	var top := m.run_speed if m.move_run else m.walk_speed
	if m is SimMech:
		if _legs_gone(m):
			return 0.0
		if _one_leg_gone(m):
			top = m.walk_speed * 0.5
	if m.uses_heat:
		top *= SimHeat.speed_factor(rules, m)
	return top


func _legs_gone(m: SimMech) -> bool:
	return m.damage_state[SimMech.Body.LLEG] == SimMech.DamageState.DESTROYED \
		and m.damage_state[SimMech.Body.RLEG] == SimMech.DamageState.DESTROYED


func _one_leg_gone(m: SimMech) -> bool:
	return (m.damage_state[SimMech.Body.LLEG] == SimMech.DamageState.DESTROYED) != \
		(m.damage_state[SimMech.Body.RLEG] == SimMech.DamageState.DESTROYED)


## Range to close to on an attack order: the longest working weapon's reach.
func attack_range(m: SimUnit) -> float:
	var best := 0.0
	for w in m.weapon_indices():
		if m.items[w]["disabled"] or m.weapon_shots(w) == 0:
			continue
		var span: Array = rules.weapon_ranges[rules.range_index(m.weapon(w)["range"])]
		best = maxf(best, float(span[1]))
	return maxf(best * 0.9, 20.0)


# --- combat -----------------------------------------------------------------

func _combat(m: SimUnit) -> void:
	if not m.exists or not m.awake or m.ejected or m.is_disabled() or m.status != SimUnit.Status.NORMAL or m.num_weapons == 0:
		return
	if m is SimMech and m.fallen:
		return
	var target := _pick_target(m)
	if target == null:
		return
	m.current_target = target
	if absf(m.rel_facing_to(target.position)) > fire_arc(m):
		return
	for w in m.weapon_indices():
		if not m.is_weapon_ready(w, time) or m.weapon_shots(w) == 0:
			continue
		if rules.heat_enabled and m.uses_heat and not m.ignore_heat_discipline:
			var after := 30.0 * (m.heat + float(m.weapon(w)["heat"])) / m.heat_capacity
			if after > fire_discipline_level:
				continue
		if SimCombat.attack_chance(rules, m, w, target) < 0.0:
			continue
		var shot := SimCombat.fire_weapon(rules, rng, m, w, target, time)
		if not shot["fired"]:
			continue
		var form: String = m.items[w]["form"]
		var speed: float = projectile_speed.get(form, 0.0)
		var flight := m.distance_to(target.position) / speed if speed > 0.0 else 0.0
		projectiles.append({"shot": shot, "target": target.id, "from": m.id, "impact_time": time + flight, "form": form})
		target.last_attacker = m
		target.last_attacked_time = time
		events.append({"type": "shot", "from": m.id, "to": target.id, "weapon": w, "form": form,
			"hit": shot["hit"], "location": shot["location"], "flight": flight})


func _pick_target(m: SimUnit) -> SimUnit:
	if m.order in [Order.ATTACK, Order.GUARD] and m.order_target and not m.order_target.is_disabled():
		return m.order_target
	var reach := attack_range(m) / 0.9
	if m.current_target and not m.current_target.is_disabled() \
			and m.distance_to(m.current_target.position) <= reach:
		return m.current_target
	# Fire at will (nearest armed enemy in reach): units without a scripted brain, the player brain, and
	# scripted units whose brain has ordered an attack. In the original a brain picks its own targets
	# (NewScan + CoreAttack, warrior.cpp coreScan); a brain that never engages (mc2_17's camera dummies)
	# never fires. Auto-firing those started mc2_17's battle ~75 s early (I12). Engaged brains keep the
	# fallback because the port's patrol brains re-scan less often than the original's.
	if m.brain != null and not m.brain_engaged and m.brain_name.to_lower() != "pbrain":
		return null
	if m.engage_m > 0.0:
		reach = minf(reach, m.engage_m)
	var best: SimUnit = null
	var best_d := INF
	var unarmed: SimUnit = null  # the AI's fallback: its brains scan for any enemy mover (warrior.cpp coreScan)
	var unarmed_d := INF
	for e in enemies_of(m):
		var d := m.distance_to(e.position)
		if d > reach:
			continue
		if e.num_weapons == 0:
			# unarmed units (trucks, transports, mobile HQs): the player's units engage them only on an explicit
			# order (C4); AI units take them when nothing armed is in reach, so a lone repair truck cannot hold a
			# mission open forever (I31)
			if not m.is_player and d < unarmed_d:
				unarmed = e
				unarmed_d = d
			continue
		if d < best_d:
			best = e
			best_d = d
	return best if best else unarmed


func _land_projectiles() -> void:
	var still: Array[Dictionary] = []
	for p in projectiles:
		if p["impact_time"] > time + 0.0001:
			still.append(p)
			continue
		var target := units[p["target"]]
		SimCombat.apply_shot(rules, rng, target, p["shot"], time)
		if p["shot"]["hit"]:
			events.append({"type": "impact", "unit": target.id, "from": p.get("from", -1), "location": p["shot"]["location"],
				"damage": p["shot"]["damage"], "form": p.get("form", "")})
	projectiles = still
