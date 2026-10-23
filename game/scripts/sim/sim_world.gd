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
var force_movie_end := false  # the player pressed Esc during the cinematic (ABL forceMovieEnd)
var fire_discipline_level := 20  # don't fire a weapon that would push heat past this level
var projectile_speed := {"EnergyWeapon": 0.0, "BallisticWeapon": 450.0, "MissileWeapon": 160.0, "Weapon": 450.0}

var _combat_clock := 0.0

# --- sight (I90, I91) ---------------------------------------------------------------------
## VisualRangeTable is 9 at every altitude, times 25 m (gameobj.cpp:1881-1897, gamesys.fit:29).
const VISUAL_RANGE_M := 225.0
## LOS and contact results are reused for this long. The original recomputes them every frame
## (with a per-frame mover LOS table, gameobj.cpp:1910-1935); missions have dozens of units, so
## the port rate-limits instead.
const SIGHT_PERIOD := 0.5
const FALLBACK_LOS_M := 3.0  # 15 wu (mover.cpp:3490)
var _los_cache := {}  # (viewer id, target id) -> Vector2(expires, seen)
var _contact_cache := {}  # (team, unit id) -> Vector2(expires, contact)
static var _los_heights: Dictionary = {}


func _init(sim_rules: SimRules, sim_map: SimMap, seed_value: int = 1) -> void:
	rules = sim_rules
	map = sim_map
	rng = SimRng.new(seed_value)


func add_unit(u: SimUnit) -> SimUnit:
	u.id = units.size()
	_movers_at = -1.0
	u.unlimited_ammo = rules.unlimited_ammo
	u.attack_radius_m = rules.default_attack_radius
	u.order = Order.HOLD
	u.prev_position = u.position
	u.prev_facing = u.facing
	units.append(u)
	return u


## Hostile units that can be auto-targeted (movers only; structures need an order).
func enemies_of(m: SimUnit) -> Array[SimUnit]:
	var out: Array[SimUnit] = []
	for o in movers():
		if o.team != m.team and o.exists and not o.is_disabled():
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
	m.attack_goal = null


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
			_update_turret(m, dt)
			_mine_check(m, dt)
		elif m is SimTurret:
			m.update(self, dt)
		elif m is SimStructure and m.parent != null:
			_follow_parent(m)
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
			elif m is SimTurret and m.is_destroyed() and m.explosion_damage > 0.0:
				explosion(m.position, m.explosion_damage, m.explosion_radius_m, m)  # turret.cpp:2198


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
	var cruising := m.cruise
	m.cruise = 0.0  # standing still unless the move below runs
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
	m.cruise = cruising
	var to_goal: Vector2 = goal - m.position
	var dist := to_goal.length()
	var desired := rad_to_deg(atan2(to_goal.x, to_goal.y))  # 0 = north, clockwise
	var diff := wrapf(desired - m.facing, -180.0, 180.0)
	var max_turn := m.turn_rate * dt
	m.facing = wrapf(m.facing + clampf(diff, -max_turn, max_turn), 0.0, 360.0)
	var top := max_speed(m)
	var align := clampf(1.0 - (absf(diff) - 30.0) / 60.0, 0.0, 1.0)  # slow when turning hard
	m.speed = minf(top * align, dist / dt)
	if rules.slew and m.max_accel > 0.0:
		# vehicles gain speed at MaxAccel (gvehicl.cpp:2977-2993); the stop at a goal stays immediate
		m.speed = minf(m.speed, m.cruise + m.max_accel * dt)
	m.cruise = m.speed
	m.position += Vector2(sin(deg_to_rad(m.facing)), cos(deg_to_rad(m.facing))) * m.speed * dt
	if m.speed <= 0.01:
		m.body_state = SimMech.BodyState.STANDING
	elif m is SimMech and _one_leg_gone(m):
		m.body_state = SimMech.BodyState.LIMPING
	elif m.speed > m.walk_speed + 0.5:
		m.body_state = SimMech.BodyState.RUNNING
	else:
		m.body_state = SimMech.BodyState.WALKING


## BattleMech::updateTorso / GroundVehicle::updateTurret: turn the torso or turret toward the
## current target (back to the front with none) at its yaw rate when the target is outside the
## fire arc, within its twist limit (gvehicl.cpp:2937-2961).
func _update_turret(m: SimUnit, dt: float) -> void:
	if not rules.slew or m.is_disabled() or m.status != SimUnit.Status.NORMAL:
		return
	var t: SimUnit = m.order_target if m.order in [Order.ATTACK, Order.GUARD] and m.order_target else m.current_target
	var want := 0.0
	if t and not t.is_disabled():
		want = m.rel_facing_to(t.position)
	var off := wrapf(want - m.turret_rel, -180.0, 180.0)
	if absf(off) <= m.fire_arc_half and t != null:
		return
	if t == null and absf(m.turret_rel) <= m.fire_arc_half:
		return
	var step := clampf(off, -m.turret_rate * dt, m.turret_rate * dt)
	var lim := m.max_torso_yaw
	m.turret_rel = clampf(m.turret_rel + step, -lim, lim) if lim < 180.0 else wrapf(m.turret_rel + step, -180.0, 180.0)


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
	var twist := float(m.max_torso_yaw)
	if rules.slew and m.turret_rate <= 0.0:
		twist = 0.0  # no yaw rate (the copters' TorsoYawRate 0): the body has to face the target
	return minf(twist + m.fire_arc_half, 180.0)


## Next point to walk to, or null. Advances the path; handles attack approach.
func _current_goal(m: SimUnit) -> Variant:
	if m.order == Order.GUARD:
		return _guard_goal(m)
	if m.order == Order.ATTACK:
		var t: SimUnit = m.order_target
		if t == null or t.is_disabled():
			order_hold(m)
			return null
		if not m.attack_pursue:
			m.path = PackedVector2Array()
			return null
		if rules.attack_goals:
			_attack_goal_path(m, t)
		else:
			if m.distance_to(t.position) <= attack_range(m) and _can_fire_on(m, t):
				m.path = PackedVector2Array()
				return null
			if m.path.is_empty() or time >= m.repath_time:
				if m.distance_to(t.position) <= attack_range(m):
					# in reach without a line of fire (behind a building or a crest): walk to a spot
					# that has one (the attack tactic repositions on NOT_LOCKED)
					m.path = _sight_position_path(m, t)
				else:
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
		if m.distance_to(t.position) <= attack_range(m) and _can_fire_on(m, t):
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


# --- group goals and attack positions (group.cpp, mover.cpp calcMoveGoal) ----------------

const GOALMAP_DIM := 61  # GOALMAP_DIM / GOALMAP_CELL_DIM (group.cpp:399, mover.cpp:123)
const MAX_ATTACK_CELLRANGE := 30  # mover.h:592
const OPTIMAL_INCREMENTS := 32  # Mover::initOptimalCells(32) (mission.cpp:2952)
const MAX_MOVE_GOALS := 60  # mover.cpp:4089; MaxMoveGoalChecks = 60 (mover.cpp:133)
## gamesys Mover:General OptimalRangePoints (20, 45, 100, 100, 160) and the tie table
## (mover.cpp:318-336): short, medium, long, short-medium, medium-long.
var optimal_range_points: Array = [20.0, 45.0, 100.0, 100.0, 160.0]
const OPTIMAL_RANGE_TIE := [255, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
	4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]


## MoverGroup::calcMoveGoals (group.cpp:401-526): goals for n movers around a clicked point. A
## uniform-cost flood over the passable cells of a 61 x 61 window, from the goal cell outwards
## (4 directions); a cell becomes a goal if nobody's claimed goal has marked it as a neighbour,
## and each claimed goal marks its 8 neighbours. The original marks the neighbours of
## (row, row + dc) instead of (row, col + dc) (group.cpp:483, `nCol = curRow + ...`); that is kept,
## so only goals on the window's diagonal mark theirs correctly. The first goal is the click
## itself, the next ones about two cells out (17 m), later ones may sit side by side.
func group_move_goals(goal: Vector2, n: int, hover := false) -> Array:
	var out: Array = []
	if n <= 0:
		return out
	var gc := map.cell_of(goal)
	var half := GOALMAP_DIM / 2
	var size := GOALMAP_DIM * GOALMAP_DIM
	var open := PackedByteArray()
	open.resize(size)
	var no_neighbour := PackedByteArray()
	no_neighbour.resize(size)
	no_neighbour.fill(1)
	var seen := PackedByteArray()
	seen.resize(size)
	for r in GOALMAP_DIM:
		for c in GOALMAP_DIM:
			var cell := Vector2i(gc.x - half + c, gc.y - half + r)
			open[r * GOALMAP_DIM + c] = 1 if map.in_bounds(cell) and map.is_walkable(cell, hover) else 0
	var queue: Array[int] = [half * GOALMAP_DIM + half]  # equal costs: a FIFO is the priority queue
	seen[queue[0]] = 1
	var head := 0
	while head < queue.size():
		var idx: int = queue[head]
		head += 1
		var r := idx / GOALMAP_DIM
		var c := idx % GOALMAP_DIM
		if open[idx] == 1 and no_neighbour[idx] == 1:
			no_neighbour[idx] = 0  # GOALFLAG_AVAILABLE cleared
			out.append(map.cell_center(Vector2i(gc.x - half + c, gc.y - half + r)))
			if out.size() == n:
				break
			for d in [Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1), Vector2i(1, 1), Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, -1)]:
				var nr: int = r + d.x
				var nc: int = r + d.y  # sic (group.cpp:483)
				if nr >= 0 and nc >= 0 and nr < GOALMAP_DIM and nc < GOALMAP_DIM:
					no_neighbour[nr * GOALMAP_DIM + nc] = 0
		for d in [Vector2i(-1, 0), Vector2i(0, 1), Vector2i(1, 0), Vector2i(0, -1)]:
			var sr: int = r + d.x
			var sc: int = c + d.y
			if sr < 0 or sc < 0 or sr >= GOALMAP_DIM or sc >= GOALMAP_DIM:
				continue
			var sidx := sr * GOALMAP_DIM + sc
			if open[sidx] == 1 and seen[sidx] == 0:
				seen[sidx] = 1
				queue.append(sidx)
	return out


## Mover::calcOptimalRange (mover.cpp:5826-5884): the range point (gamesys OptimalRangePoints)
## covered by the most damage per second of working weapons; ties by OptimalRangeTieTable.
func optimal_fire_range(m: SimUnit) -> float:
	var totals := [0.0, 0.0, 0.0, 0.0, 0.0]
	var any := false
	for w in m.weapon_indices():
		if m.items[w]["disabled"] or m.weapon_shots(w) == 0:
			continue
		var wpn := m.weapon(w)
		var span: Array = rules.weapon_ranges[rules.range_index(wpn.get("range", "short"))]
		var dps := float(wpn.get("damage", 0.0)) / maxf(float(wpn.get("recycle", 1.0)), 0.01)
		any = true
		for i in 5:
			var pt: float = optimal_range_points[i]
			if pt > float(span[0]) and pt <= float(span[1]):
				totals[i] += dps
	if not any:
		return 0.0
	var best := 0
	for i in 5:
		if totals[i] > totals[best]:
			best = i
	if totals[best] <= 0.0:
		return 0.0
	var tie := 0
	for i in 5:
		if totals[i] == totals[best]:
			tie |= 1 << i
	if tie != (1 << best):
		best = OPTIMAL_RANGE_TIE[tie]
		if best == 255:
			return 0.0
	return optimal_range_points[best]


## Mover min/max fire range: the weapons' span (calcFireRanges, as turret.cpp:2215).
func fire_range_span(m: SimUnit) -> Vector2:
	var lo := INF
	var hi := 0.0
	for w in m.weapon_indices():
		if m.items[w]["disabled"] or m.weapon_shots(w) == 0:
			continue
		var span: Array = rules.weapon_ranges[rules.range_index(m.weapon(w).get("range", "short"))]
		lo = minf(lo, float(span[0]))
		hi = maxf(hi, float(span[1]))
	return Vector2(0.0 if lo == INF else lo, hi)


## Mover::calcMoveGoal for an attack order (mover.cpp:4364-4900): where to stand to fire on t.
## Over a 61 x 61 cell map centred on the target, cells score:
##   +500 on the ring at the pilot's fire range (FIRERANGE_OPTIMAL: the optimal range, in cells,
##        32 bearings; optimalCells),
##   -500 beyond the longest weapon's reach and inside the shortest's minimum,
##   +100 in the 3 x 3 round the target for a non-player order,
##   -1 per cell (Manhattan) from the attacker, -100 on a group mate's goal,
##   -10000 where it can't stand (impassable, off-map; deep water unless a hovercraft), and
##   -10000 on its own cell when it must move somewhere else (no line of fire there).
## The 60 best are tried in order and the first with a line of sight to t wins; failing that, the
## best (calcBestGoalFromTarget is not ported). Area connectivity is left to the path search.
func attack_goal(m: SimUnit, t: SimUnit, somewhere_else := false) -> Vector2:
	var cs := map.cell_m
	var tc := map.cell_of(t.position)
	var half := GOALMAP_DIM / 2
	var span := fire_range_span(m)
	var fr := optimal_fire_range(m)
	var fire_cells := clampi(int(fr / cs), 1, MAX_ATTACK_CELLRANGE - 1) if fr > 0.0 else 2
	var min_cells := mini(int(span.x / cs), MAX_ATTACK_CELLRANGE - 1)
	var max_cells := mini(int(span.y / cs), MAX_ATTACK_CELLRANGE - 1)
	var size := GOALMAP_DIM * GOALMAP_DIM
	var wt := PackedInt32Array()
	wt.resize(size)
	var ring := {}
	for i in OPTIMAL_INCREMENTS:
		var a := deg_to_rad(360.0 / OPTIMAL_INCREMENTS * i)
		var dr := sin(a) * fire_cells
		var dc := cos(a) * fire_cells
		ring[Vector2i(int(dc - 0.5) if dc < 0.0 else int(dc + 0.5), int(dr - 0.5) if dr < 0.0 else int(dr + 0.5))] = true
	var sc := map.cell_of(m.position) - tc + Vector2i(half, half)
	sc = Vector2i(clampi(sc.x, 0, GOALMAP_DIM - 1), clampi(sc.y, 0, GOALMAP_DIM - 1))
	var mates: Dictionary = {}
	if m.group >= 0:
		for o in movers():
			if o != m and o.team == m.team and o.commander == m.commander and o.group == m.group and o.attack_goal != null:
				mates[map.cell_of(o.attack_goal)] = true
	for r in GOALMAP_DIM:
		for c in GOALMAP_DIM:
			var off := Vector2i(c - half, r - half)
			var cell := tc + off
			var idx := r * GOALMAP_DIM + c
			if not map.in_bounds(cell):
				wt[idx] = -999999
				continue
			var w := 0
			var d := sqrt(float(off.x * off.x + off.y * off.y))
			if d > max_cells + 0.5 and d < MAX_ATTACK_CELLRANGE - 0.5:
				w -= 500
			if min_cells > 0 and d < min_cells - 0.5:
				w -= 500
			if ring.has(off):
				w += 500
			if not m.is_player and absi(off.x) <= 1 and absi(off.y) <= 1:
				w += 100
			w -= absi(c - sc.x) + absi(r - sc.y)
			if mates.has(cell):
				w -= 100
			if not map.is_walkable(cell, m.hover):
				w -= 10000
			wt[idx] = w
	if somewhere_else:
		wt[sc.y * GOALMAP_DIM + sc.x] -= 10000
	var cands: Array = []
	for idx in size:
		if wt[idx] > -10000:
			cands.append(idx)
	cands.sort_custom(func(a, b): return wt[a] > wt[b])
	var h := los_height(m)
	var th := los_height(t)
	var ext := sight_radius(t) if t is SimStructure else 0.0
	for k in mini(cands.size(), MAX_MOVE_GOALS):
		var idx: int = cands[k]
		var p := map.cell_center(tc + Vector2i(idx % GOALMAP_DIM - half, idx / GOALMAP_DIM - half))
		if p.distance_to(t.position) <= visual_range(m) and map.line_of_sight(p, h, t.position, th, ext, 0.0, rules.max_tree_los):
			return p
	if cands.is_empty():
		return map.nearest_walkable(t.position, m.hover)
	var b: int = cands[0]
	return map.cell_center(tc + Vector2i(b % GOALMAP_DIM - half, b / GOALMAP_DIM - half))


## The attack order's movement: walk to the attack goal and fire from it (and on the way). A new
## goal when the target has moved two cells from where it was picked, or on arriving without a
## line of fire (MOVEPARAM_SOMEWHERE_ELSE); at most every 2 s.
func _attack_goal_path(m: SimUnit, t: SimUnit) -> void:
	var stale: bool = m.attack_goal == null or t.position.distance_to(m.attack_goal_from) > 2.0 * map.cell_m
	var arrived: bool = m.attack_goal != null and m.path.is_empty() and m.position.distance_to(m.attack_goal) <= map.cell_m
	var blind := arrived and not _can_fire_on(m, t)
	if not (stale or blind) or (time < m.repath_time and m.attack_goal != null):
		return
	m.attack_goal = attack_goal(m, t, blind)
	m.attack_goal_from = t.position
	m.repath_time = time + 2.0
	m.path_index = 0
	if map.cell_of(m.attack_goal) == map.cell_of(m.position):
		m.path = PackedVector2Array()
		return
	m.path = map.find_path(m.position, m.attack_goal, m.hover)
	if m.path.is_empty():
		m.path = _firing_position_path(m, t)


## In range is not enough with line of sight on: a pursuing attacker keeps closing until it
## (or, for an indirect-fire weapon, a team mate) can see the target (calcWeaponsStatus
## NOT_LOCKED, warrior.cpp:3396-3414).
func _can_fire_on(m: SimUnit, t: SimUnit) -> bool:
	if line_of_sight(m, t):
		return true
	for w in m.weapon_indices():
		if int(m.items[w]["master_id"]) in rules.indirect_fire_ids:
			return team_line_of_sight(m.team, t)
	return false


## The nearest reachable cell within weapon reach of t that can see it (SimMap.line_of_sight
## from this unit's sight height), on rings of 16 bearings; empty if none.
func _sight_position_path(m: SimUnit, t: SimUnit) -> PackedVector2Array:
	var reach := attack_range(m)
	var h := los_height(m)
	var th := los_height(t)
	var ext := sight_radius(t) if t is SimStructure else 0.0
	var cands := []
	for r in [reach * 0.35, reach * 0.6, reach * 0.85]:
		for k in 16:
			var p: Vector2 = t.position + Vector2.from_angle(TAU * k / 16.0) * maxf(r, 20.0 + ext)
			var c := map.cell_of(p)
			if not map.in_bounds(c) or not map.is_walkable(c, m.hover):
				continue
			if map.cell_of(p) == map.cell_of(m.position) or p.distance_to(m.position) < map.cell_m * 1.5:
				continue  # where it stands already has no line of fire
			if map.line_of_sight(p, h, t.position, th, ext, 0.0, rules.max_tree_los):
				cands.append(p)
	cands.sort_custom(func(a, b): return a.distance_to(m.position) < b.distance_to(m.position))
	for p in cands.slice(0, 6):
		var path := map.find_path(m.position, p, m.hover)
		if not path.is_empty():
			return path
	# no spot with a line of fire in reach: close in on the target itself
	return map.find_path(m.position, map.nearest_walkable(t.position, m.hover), m.hover)


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
	if m is SimTurret:
		return  # turrets fire from their own update (SimTurret.update)
	if not m.exists or not m.awake or m.ejected or m.is_disabled() or m.status != SimUnit.Status.NORMAL or m.num_weapons == 0:
		return
	if m is SimMech and m.fallen:
		return
	var target := _pick_target(m)
	if target == null:
		return
	m.current_target = target
	if rules.slew:
		# weaponLocked: the bearing from the torso or turret, within FireArc/2 (warrior.cpp:3393-3410)
		if absf(wrapf(m.rel_facing_to(target.position) - m.turret_rel, -180.0, 180.0)) > m.fire_arc_half:
			return
	elif absf(m.rel_facing_to(target.position)) > fire_arc(m):
		return
	# calcWeaponsStatus (warrior.cpp:3396-3414): direct fire needs line of sight; indirect-fire
	# weapons may fire on any team mate's (I91)
	var direct := line_of_sight(m, target)
	var team_seen := -1
	for w in m.weapon_indices():
		if not m.is_weapon_ready(w, time) or m.weapon_shots(w) == 0:
			continue
		if rules.heat_enabled and m.uses_heat and not m.ignore_heat_discipline:
			var after := 30.0 * (m.heat + float(m.weapon(w)["heat"])) / m.heat_capacity
			if after > fire_discipline_level:
				continue
		if SimCombat.attack_chance(rules, m, w, target) < 0.0:
			continue
		if not direct:
			if not (int(m.items[w]["master_id"]) in rules.indirect_fire_ids):
				continue
			if team_seen < 0:
				team_seen = 1 if team_line_of_sight(m.team, target) else 0
			if team_seen == 0:
				continue
		var node := -1
		if rules.vehicle_weapon_nodes and m is SimVehicle and m.weapon_nodes >= 0:
			node = m.pick_weapon_node()
			if not m.weapon_node_allows(node, time):
				continue  # O1: no usable weapon node (gvehicl.cpp:4610-4616)
		var shot := SimCombat.fire_weapon(rules, rng, m, w, target, time)
		if not shot["fired"]:
			continue
		if node >= 0:
			m.use_weapon_node(node, time)
		_launch(m, w, target, shot)


## A fired shot: the projectile in flight and the view's event. Area-effect weapons (the Long
## Tom, Swarm LRMs) carry their blast instead of a direct hit (weaponbolt.cpp:762-794).
func _launch(m: SimUnit, w: int, target: SimUnit, shot: Dictionary) -> void:
	var form: String = m.items[w]["form"]
	var speed: float = projectile_speed.get(form, 0.0)
	var flight := m.distance_to(target.position) / speed if speed > 0.0 else 0.0
	var p := {"shot": shot, "target": target.id, "from": m.id, "impact_time": time + flight, "form": form}
	var mid := int(m.items[w]["master_id"])
	if rules.area_effect_weapons and rules.area_effect.has(mid):
		p["area"] = rules.area_effect[mid]
		p["shot"] = shot.duplicate()
		p["shot"]["hit"] = false  # damage is done by the explosion, not by the hit
		p["hit"] = shot["hit"]
	projectiles.append(p)
	target.last_attacker = m
	target.last_attacked_time = time
	events.append({"type": "shot", "from": m.id, "to": target.id, "weapon": w, "form": form,
		"hit": shot["hit"], "location": shot["location"], "flight": flight})


## Turret::fireWeapon (turret.cpp:1352-1600): line of sight to the target (a team mate's for an
## indirect-fire weapon) or no shot and no recycle; then the turret's own to-hit, the recycle and
## a hit of the weapon's damage (missiles fire 1 missile of the CSV damage: getWeaponAmmoAmount 1).
func turret_fire(t: SimTurret, w: int, target: SimUnit) -> void:
	var mid := int(t.items[w]["master_id"])
	if not line_of_sight(t, target):
		if not (mid in rules.indirect_fire_ids) or not team_line_of_sight(t.team, target):
			return
	var chance := t.turret_attack_chance(rules, w, target)
	if chance < 0.0:
		return
	var weapon: Dictionary = t.items[w]["component"].get("weapon", {})
	var roll := rng.roll(100)
	t.items[w]["ready_time"] = time + float(weapon.get("recycle", 1.0))
	var shot := {"fired": true, "reason": "", "chance": chance, "roll": roll, "hit": roll < int(chance),
		"location": -1, "damage": 0.0, "master_id": mid}
	if shot["hit"]:
		shot["damage"] = float(weapon.get("damage", 0.0))
		if target is SimMech:
			shot["location"] = SimCombat.hit_location(rules, rng, target, t.position)
		else:
			shot["location"] = target.roll_hit_location(rules, rng, t.position)
	_launch(t, w, target, shot)


## Mines (support-powers.md 3.5): a minelayer in minelaying mode mines each new cell it has been
## in for MineWaitTime, spending one mine (one point of its turret armour) per mine
## (gvehicl.cpp:3605-3637). Any other mech or vehicle over 35 t that enters a laid mine sets it
## off: 12 damage, a mech in its bottom section from a random side (BattleMech::mineCheck,
## mech.cpp:3731-3778; gvehicl.cpp:1355-1420). Jumping mechs and minelayers don't; no team check.
func _mine_check(m: SimUnit, dt: float) -> void:
	if not m.exists or m.is_disabled() or m.order == Order.JUMP:
		return
	var c := map.cell_of(m.position)
	if m is SimVehicle and m.mine_stock > 0:
		if m.order != Order.MOVE:
			m.laying_mines = false
		if m.laying_mines and c != m.mine_cell:
			m.mine_dwell += dt
			if m.mine_dwell > float(rules.mine["wait_time"]):
				m.mine_cell = c
				m.mine_dwell = 0.0
				map.set_mine(c, 1)
				m.mine_stock -= 1
				m.take_hit(rules, rng, 1.0, SimVehicle.Section.TURRET, -2, time)  # the stock is the turret armour
				events.append({"type": "mine_laid", "at": map.cell_center(c), "unit": m.id})
		return
	if map.mine_at(c) != 1:
		return
	if m is SimVehicle and m.mine_sweeper:
		map.set_mine(c, 2)  # swept (gvehicl.cpp:1363-1383)
		return
	if m.tonnage <= float(rules.mine["min_tonnage"]):
		return
	map.set_mine(c, 2)
	var side := m.position + Vector2.from_angle(deg_to_rad(float(rng.roll(360)))) * 10.0  # entryAngle random
	var loc: int
	if m is SimMech:
		loc = SimCombat.hit_location(rules, rng, m, side, SimRules.Section.BOTTOM)
	else:
		loc = m.roll_hit_location(rules, rng, side)
	var dmg := float(rules.mine["damage"])
	SimCombat.apply_shot(rules, rng, m, {"hit": true, "damage": dmg, "location": loc, "master_id": -2}, time)
	events.append({"type": "mine", "at": map.cell_center(c), "unit": m.id})
	events.append({"type": "impact", "unit": m.id, "from": -1, "location": loc, "damage": dmg, "form": "mine"})
	explosion(m.position, float(rules.mine["splash_damage"]), float(rules.mine["splash_range"]), m)


## A child building (a sensor tower) takes its control's team while the control stands, and
## sleeps once it is gone (bldng.cpp:878-912).
func _follow_parent(s: SimStructure) -> void:
	var p := s.parent
	if p.is_destroyed() or p.is_disabled() or not p.awake:
		s.awake = false
	elif p.team != s.team:
		s.team = p.team
		s.commander = p.commander


## ObjectManager::createExplosion + ExplosionType::handleCollision (objmgr.cpp:2661,
## carnage.cpp:343-436): every mover within the radius takes the damage at an artillery hit
## location; buildings take it whole; a turret only within its little extent of the radius.
## A mine in the blast's cell goes off (weaponbolt.cpp:826).
func explosion(at: Vector2, damage: float, radius_m: float, source: SimUnit = null) -> void:
	if damage <= 0.0 or radius_m <= 0.0:
		return
	for u in units:
		if not u.exists or u.is_destroyed() or u == source:
			continue
		var d := u.position.distance_to(at)
		if u is SimTurret:
			if d - u.little_extent_m > radius_m:
				continue
		elif u is SimStructure:
			if d > radius_m + u.extent_m:
				continue
		elif d > radius_m:
			continue
		var loc: int
		if u is SimMech:
			loc = SimCombat.hit_location(rules, rng, u, at)
		else:
			loc = u.roll_hit_location(rules, rng, at)
		SimCombat.apply_shot(rules, rng, u, {"hit": true, "damage": damage, "location": loc, "master_id": -3}, time)
		if source and u.is_mover():
			u.last_attacker = source
			u.last_attacked_time = time
		events.append({"type": "impact", "unit": u.id, "from": source.id if source else -1, "location": loc,
			"damage": damage, "form": "blast"})
	var c := map.cell_of(at)
	if map.mine_at(c) == 1:
		map.set_mine(c, 2)
		events.append({"type": "mine", "at": map.cell_center(c), "unit": -1})


func _pick_target(m: SimUnit) -> SimUnit:
	if m.current_target and m.current_target.team == m.team:
		m.current_target = null  # it changed sides (a captured turret or building): not a target now
	if m.order in [Order.ATTACK, Order.GUARD] and m.order_target and m.order_target.team == m.team:
		order_hold(m)
	if m.order in [Order.ATTACK, Order.GUARD] and m.order_target and not m.order_target.is_disabled():
		return m.order_target
	if m.brain != null and rules.brain_target_only:
		# combatDecisionTree (warrior.cpp:3493, 3532-3538): a pilot fires only at its last target,
		# which it drops beyond its attack radius when it has no combat order (F6). The target is
		# whatever its brain (or the player) last attacked.
		var last := m.current_target
		if last == null or last.is_disabled() or not last.exists:
			return null
		if m.distance_to(last.position) > m.attack_radius_m:
			m.current_target = null
			return null
		return last
	var reach := attack_range(m) / 0.9
	if m.current_target and not m.current_target.is_disabled() \
			and m.distance_to(m.current_target.position) <= reach:
		return m.current_target
	# Fire at will (nearest armed enemy in reach): units without a scripted brain, and scripted units
	# whose brain has ordered an attack. In the original a brain picks its own targets (NewScan +
	# CoreAttack, warrior.cpp coreScan); a brain that never engages (mc2_17's camera dummies) never
	# fires. Engaged brains keep the fallback because the port's patrol brains re-scan less often than
	# the original's. The player brain gets no fallback: pbrain's own FireAtWill (orders.abx:2418) picks
	# its targets, and with SetNotTargetingMod(0.0) (pbrain.abl:110) it rates an enemy that is
	# targeting nobody at 0 (orders.abx:1115-1117), so the lance leaves idle units alone and engages
	# only units that are fighting, plus whatever it is ordered to attack or is shot by (I12: mc2_17's
	# lance opened fire on the idle cinematic dummies, starting the battle before the betrayal). An
	# attack order does not change that: the brain keeps choosing through FireAtWill afterwards.
	if m.brain != null and (not m.brain_engaged or m.brain_name.to_lower() == "pbrain"):
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
		if p.has("area"):
			# hit: the blast at the target; a miss lands 25 wu (5 m) off it (gvehicl.cpp:4883-4892)
			var at: Vector2 = target.position if p["hit"] else target.position + Vector2(5.0, 0.0)
			events.append({"type": "blast", "at": at, "radius": float(p["area"][1]), "from": p.get("from", -1)})
			explosion(at, float(p["area"][0]), float(p["area"][1]), units[p["from"]] if p.get("from", -1) >= 0 else null)
			continue
		SimCombat.apply_shot(rules, rng, target, p["shot"], time)
		if p["shot"]["hit"]:
			events.append({"type": "impact", "unit": target.id, "from": p.get("from", -1), "location": p["shot"]["location"],
				"damage": p["shot"]["damage"], "form": p.get("form", "")})
	projectiles = still


# --- sight: line of sight and contacts (I90, I91) ------------------------------------------

## Sight point height above the ground (getLOSPosition): a mover's lowest weapon node (mechs and
## vehicles, mover.cpp:3442-3498), a turret's first weapon node (turret.cpp:1235), a building's
## half height (bldng.h:244-257; the cell's local height stands in for the model's top).
func los_height(u: SimUnit) -> float:
	if u.los_height_m < 0.0:
		if _los_heights.is_empty() and FileAccess.file_exists("res://data/los_heights.json"):
			_los_heights = JSON.parse_string(FileAccess.get_file_as_string("res://data/los_heights.json"))
		var h := FALLBACK_LOS_M
		if u is SimMech:
			h = float(_los_heights.get("mechs", {}).get(u.model, FALLBACK_LOS_M))
		elif u is SimVehicle:
			h = float(_los_heights.get("vehicles", {}).get(u.model, FALLBACK_LOS_M))
		elif u is SimTurret:
			h = float(_los_heights.get("turrets", {}).get(u.model, FALLBACK_LOS_M))
		elif u is SimStructure:
			h = 0.5 * map.local_height(map.cell_of(u.position))
		u.los_height_m = h
	return u.los_height_m + u.jump_alt


var _movers_at := -1.0
var _movers: Array[SimUnit] = []
var _sensors: Array[SimUnit] = []  # structures with a team sensor


## The movers (and sensor towers), listed once per tick: sight and turret scans walk these
## instead of every map object.
func movers() -> Array[SimUnit]:
	_list_units()
	return _movers


func _list_units() -> void:
	if _movers_at == time:
		return
	_movers_at = time
	_movers.clear()
	_sensors.clear()
	for u in units:
		if u.is_mover():
			_movers.append(u)
		elif u is SimStructure and (u as SimStructure).tower_sensor_m > 0.0:
			_sensors.append(u)


## A building's radius for line of sight. The original passes the appearance's bounding radius
## (getAppearRadius, gameobj.cpp:1937), which spans the model; ExtentRadius can be much smaller,
## and the walk would then end on the building's own raised cells. The model is not in the sim,
## so its footprint stands in: the cells with a local height joined to its own, out to 40 m.
func sight_radius(s: SimStructure) -> float:
	if s.sight_radius_m < 0.0:
		var c0 := map.cell_of(s.position)
		var r := s.extent_m
		var seen := {c0: true}
		var todo: Array[Vector2i] = [c0]
		while not todo.is_empty() and seen.size() < 400:
			var c: Vector2i = todo.pop_back()
			var centre := map.cell_center(c)
			if centre.distance_to(s.position) > 40.0:
				continue
			r = maxf(r, centre.distance_to(s.position) + map.cell_m * 0.5)
			for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var n: Vector2i = c + d
				if not seen.has(n) and map.local_height(n) > 0.0:
					seen[n] = true
					todo.append(n)
		s.sight_radius_m = r
	return s.sight_radius_m


## Visual range: 225 m, +20% for a Scout pilot, times the type's LOSFactor (gameobj.cpp:1881-1892).
func visual_range(u: SimUnit) -> float:
	var r := VISUAL_RANGE_M
	if u.pilot and u.pilot.has("Scout"):
		r *= 1.2
	return r * u.los_factor


## GameObject::lineOfSight (gameobj.cpp:1846-1990): within visual range, then the terrain walk
## (SimMap.line_of_sight) from a's sight point to b's. With rules.line_of_sight off, always true.
func line_of_sight(a: SimUnit, b: SimUnit) -> bool:
	if not rules.line_of_sight:
		return true
	if a.distance_to(b.position) > visual_range(a):
		return false
	var key := a.id * 16384 + b.id
	var c: Variant = _los_cache.get(key)
	if c != null and (c as Vector2).x > time:
		return (c as Vector2).y > 0.5
	if _los_cache.size() > 60000:
		_los_cache.clear()
	var ext := sight_radius(b) if b is SimStructure else 0.0
	var start_ext := sight_radius(a) if a is SimStructure else 0.0
	var seen := map.line_of_sight(a.position, los_height(a), b.position, los_height(b), ext, start_ext, rules.max_tree_los)
	_los_cache[key] = Vector2(time + SIGHT_PERIOD, 1.0 if seen else 0.0)
	return seen


## Team::teamLineOfSight (team.cpp:762-810): any working team mover sees the target. Indirect fire
## (LRMs, the Long Tom) uses it. Lookout towers (team.cpp:812-860) are not modelled.
func team_line_of_sight(team: int, b: SimUnit) -> bool:
	for f in movers():
		if f.team == team and f.exists and not f.is_disabled() and f.status != SimUnit.Status.SHUTDOWN \
				and line_of_sight(f, b):
			return true
	return false


## A team's contact (SensorSystem::calcContactStatus, Contact.cpp:257-350): a mover that is not
## disabled and that a working sensor of the team sees, by
## - visual: line of sight within visual range from a team mover with a working sensor;
## - sensor: within a team mover's fitted sensor range (Vehicle Sensors 0 m, Standard 1, Extended
##   400, Advanced 550, Cyclops 800), or a team sensor tower's, unless the target is shut down or
##   carries a working ECM suite (no signature).
## With rules.original_contacts off: the old placeholder (any team mover within 500 m).
func is_contact(team: int, m: SimUnit) -> bool:
	if not m.is_mover() or not m.exists or m.team == team:
		return false
	if not rules.original_contacts:
		for f in movers():
			if f.team == team and f.exists and f.awake and not f.is_disabled() \
					and f.position.distance_to(m.position) <= 500.0:
				return true
		return false
	if m.is_disabled():
		return false
	var key := (team + 1) * 16384 + m.id
	var c: Variant = _contact_cache.get(key)
	if c != null and (c as Vector2).x > time:
		return (c as Vector2).y > 0.5
	var seen := _contact(team, m)
	_contact_cache[key] = Vector2(time + SIGHT_PERIOD, 1.0 if seen else 0.0)
	return seen


func _contact(team: int, m: SimUnit) -> bool:
	var no_signature := m.status == SimUnit.Status.SHUTDOWN or m.has_ecm()
	_list_units()
	if not no_signature:
		for f in _sensors:
			if f.team == team and f.exists and f.sensor_works() and f.position.distance_to(m.position) <= (f as SimStructure).tower_sensor_m:
				return true
	for f in _movers:
		if f.team != team or not f.exists:
			continue
		if not f.awake or f.is_disabled() or f.hulk:
			continue
		var sr := f.sensor_range()
		if sr < 0.0:
			continue  # no working sensor: no contacts at all
		var d := f.distance_to(m.position)
		if sr > 0.0 and not no_signature and d <= sr:
			return true
		if d <= visual_range(f) and line_of_sight(f, m):
			return true
	return false
