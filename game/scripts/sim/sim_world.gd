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

enum Order { HOLD, MOVE, ATTACK }

var rules: SimRules
var map: SimMap
var rng: SimRng
var time := 0.0
var units: Array[SimUnit] = []
var projectiles: Array[Dictionary] = []  # {shot, target_id, impact_time}
var events: Array[Dictionary] = []  # drained by the view each frame
var flags: Dictionary = {}  # mission boolean flags (objectives, mission script, brains)
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

func order_move(m: SimUnit, goal: Vector2) -> bool:
	var path := map.find_path(m.position, map.nearest_walkable(goal, m.hover), m.hover)
	m.order = Order.MOVE
	m.order_target = null
	m.path = path
	m.path_index = 0
	return path.size() > 0


func order_attack(m: SimUnit, target: SimUnit) -> void:
	m.order = Order.ATTACK
	m.order_target = target
	m.path = PackedVector2Array()
	m.repath_time = 0.0


func order_hold(m: SimUnit) -> void:
	m.order = Order.HOLD
	m.order_target = null
	m.path = PackedVector2Array()


# --- tick ---------------------------------------------------------------------

func step(dt: float = TICK) -> void:
	time += dt
	for m in units:
		m.prev_position = m.position
		m.prev_facing = m.facing
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


## Standing with a target outside the fire arc: turn in place toward it.
func _face_target(m: SimUnit, dt: float) -> void:
	var t: SimUnit = m.order_target if m.order == Order.ATTACK else m.current_target
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
	if m.order == Order.ATTACK:
		var t: SimUnit = m.order_target
		if t == null or t.is_disabled():
			order_hold(m)
			return null
		if m.distance_to(t.position) <= attack_range(m):
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
	var top := m.run_speed
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
	if m.order == Order.ATTACK and m.order_target and not m.order_target.is_disabled():
		return m.order_target
	var reach := attack_range(m) / 0.9
	if m.current_target and not m.current_target.is_disabled() \
			and m.distance_to(m.current_target.position) <= reach:
		return m.current_target
	if m.engage_m > 0.0:
		reach = minf(reach, m.engage_m)
	var best: SimUnit = null
	var best_d := INF
	for e in enemies_of(m):
		if e.capturable and e.num_weapons == 0:
			continue  # unarmed capture targets (trucks, mobile HQs): only on an explicit order
		var d := m.distance_to(e.position)
		if d < best_d and d <= reach:
			best = e
			best_d = d
	return best


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
