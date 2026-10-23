extends GdUnitTestSuite
## Rules copied from the original after the 2026-10-23 fidelity check
## (docs/reports/fidelity/2026-10-23-combat.md): vehicle weapon nodes (O1, I88), unlimited
## ammo (O2, I97), contacts (I90), line of sight (I91), brain walk speed (I92) and the
## engaged brain's target (F6).

var rules: SimRules
var world: SimWorld
var origin := Vector2.ZERO


func before_test() -> void:
	rules = SimFixture.rules()
	world = SimWorld.new(rules, SimMap.load_mission("mc2_01"), 1)
	# open ground by the player's start on mc2_01
	origin = world.map.nearest_walkable(Vector2(499.2, -380.0))


func _vehicle(file: String, team: int, at: Vector2, gunnery := 60.0) -> SimVehicle:
	var v := SimVehicle.from_data(JSON.parse_string(FileAccess.get_file_as_string("res://data/vehicles/%s.json" % file)),
		rules, SimPilot.make(gunnery, 50))
	v.team = team
	v.position = at
	world.add_unit(v)
	return v


func _target_mech(at: Vector2) -> SimMech:
	var m := SimFixture.mech("atlas", rules)
	m.team = 0
	m.is_player = true
	m.position = at
	m.facing = 180.0
	m.awake = false  # a passive target: it never fires back
	world.add_unit(m)
	return m


func _shots_by(u: SimUnit, seconds: float) -> int:
	var n := 0
	var t := 0.0
	while t < seconds:
		world.step()
		t += SimWorld.TICK
		for e in world.events:
			if e["type"] == "shot" and e["from"] == u.id:
				n += 1
		world.events.clear()
	return n


# --- O1: vehicle weapon nodes -------------------------------------------------------

func test_node_counts_from_the_shapes() -> void:
	var p := _vehicle("partisan", 1, origin)
	var h := _vehicle("harasser", 1, origin + Vector2(10, 0))
	var c := _vehicle("centipede", 1, origin + Vector2(20, 0))
	assert_int(p.weapon_nodes).is_equal(4)
	assert_int(_vehicle("tankk", 1, origin + Vector2(30, 0)).weapon_nodes).is_equal(4)  # Legion
	assert_int(h.weapon_nodes).is_equal(2)
	assert_int(c.weapon_nodes).is_equal(1)


func test_least_used_node_and_the_node_three_limit() -> void:
	var p := _vehicle("partisan", 1, origin)
	assert_int(p.pick_weapon_node()).is_equal(2)  # Weapon_01 is node 2 (after 2 smoke nodes)
	p.use_weapon_node(2, 0.0)
	assert_int(p.pick_weapon_node()).is_equal(3)
	assert_bool(p.weapon_node_allows(3, 0.0)).is_true()
	p.use_weapon_node(3, 0.0)
	assert_int(p.pick_weapon_node()).is_equal(4)  # Weapon_03: least used, and above 3
	assert_bool(p.weapon_node_allows(4, 100.0)).is_false()
	var h := _vehicle("harasser", 1, origin)
	h.use_weapon_node(2, 0.0)
	h.use_weapon_node(3, 0.0)
	assert_int(h.pick_weapon_node()).is_equal(2)
	assert_bool(h.weapon_node_allows(2, 0.1)).is_false()  # still recycling (0.25 s)
	assert_bool(h.weapon_node_allows(2, 0.25)).is_true()


func test_partisan_fires_two_shots_per_mission() -> void:
	var p := _vehicle("partisan", 1, origin + Vector2(0, 50))
	_target_mech(origin)
	assert_int(_shots_by(p, 60.0)).is_equal(2)


func test_partisan_fires_freely_with_the_rule_off() -> void:
	rules.vehicle_weapon_nodes = false
	var p := _vehicle("partisan", 1, origin + Vector2(0, 50))
	_target_mech(origin)
	assert_int(_shots_by(p, 60.0)).is_greater(20)


func test_two_node_vehicle_keeps_firing() -> void:
	var h := _vehicle("harasser", 1, origin + Vector2(0, 50))
	_target_mech(origin)
	assert_int(_shots_by(h, 60.0)).is_greater(10)


# --- O2: unlimited ammo ---------------------------------------------------------------

func test_unlimited_ammo_by_default() -> void:
	var m := _target_mech(origin)
	var lrm := SimFixture.item(m, 120)
	assert_bool(m.unlimited_ammo).is_true()
	assert_int(m.weapon_shots(lrm)).is_equal(-1)
	var bins_before := m.items.map(func(i): return i["amount"])
	m.reduce_ammo(220, 5)
	assert_array(m.items.map(func(i): return i["amount"])).is_equal(bins_before)


func test_limited_ammo_when_switched_off() -> void:
	rules.unlimited_ammo = false
	var m := _target_mech(origin)
	assert_int(m.weapon_shots(SimFixture.item(m, 120))).is_equal(96)


# --- a flat test map --------------------------------------------------------------------------

func _flat_world() -> void:
	world = SimWorld.new(rules, SimFixture.flat_map(), 1)
	origin = Vector2.ZERO


# --- I90: contacts ---------------------------------------------------------------------------

func test_visual_contact_within_225_m() -> void:
	_flat_world()
	var eye := _vehicle("partisan", 0, Vector2.ZERO)  # vehicle sensors: 0 m, visual only
	var near := _vehicle("partisan", 1, Vector2(0, 200))
	var far := _vehicle("partisan", 1, Vector2(240, 0))
	assert_float(eye.sensor_range()).is_equal(0.0)
	assert_bool(world.is_contact(0, near)).is_true()
	assert_bool(world.is_contact(0, far)).is_false()
	eye.pilot.specialties["Scout"] = true  # +20%: 270 m
	world._contact_cache.clear()
	world._los_cache.clear()
	assert_bool(world.is_contact(0, far)).is_true()


func test_sensor_contact_by_fitted_sensor_but_not_through_ecm_or_shutdown() -> void:
	_flat_world()
	var eye := _vehicle("partisan", 0, Vector2.ZERO)
	var item := eye.items.filter(func(i): return i["form"] == "Sensors")[0] as Dictionary
	item["component"] = rules.component(14)  # Extended Sensors: 400 m
	var t := _vehicle("partisan", 1, Vector2(350, 0))
	assert_bool(world.is_contact(0, t)).is_true()
	world._contact_cache.clear()
	t.status = SimUnit.Status.SHUTDOWN  # no signature: only visual
	assert_bool(world.is_contact(0, t)).is_false()
	t.status = SimUnit.Status.NORMAL
	t.items.insert(0, {"component": rules.component(38), "form": "ECM", "master_id": 38, "health": 1, "disabled": false,
		"amount": 1, "ready_time": 0.0, "body_location": -1})
	t.num_other += 1
	world._contact_cache.clear()
	assert_bool(world.is_contact(0, t)).is_false()
	t.position = Vector2(150, 0)  # visual still sees an ECM carrier
	world._contact_cache.clear()
	assert_bool(world.is_contact(0, t)).is_true()


func test_a_hill_hides_a_contact() -> void:
	_flat_world()
	var eye := _vehicle("partisan", 0, Vector2.ZERO)
	var t := _vehicle("partisan", 1, Vector2(0, 150))
	assert_bool(world.is_contact(0, t)).is_true()
	var m := world.map
	for col in range(28, 33):  # a 30 m ridge across the line, 75 m north
		for row in [27, 26]:
			m.elevation_m[row * m.vertices_per_side + col] = 30.0
	world._contact_cache.clear()
	world._los_cache.clear()
	assert_bool(world.line_of_sight(eye, t)).is_false()
	assert_bool(world.is_contact(0, t)).is_false()


func test_trees_block_after_max_tree_cells() -> void:
	_flat_world()
	var m := world.map
	# MaxTreeLOSBlock (6) counts walk steps (2/3 of a cell) under the trees' height, so 3 forest
	# cells (about 4-5 steps) still let the line through and about 4 or more block it
	assert_bool(m.line_of_sight(Vector2(-100, 0), 3.0, Vector2(100, 0), 3.0)).is_true()
	for k in 3:
		var c := m.cell_of(Vector2(-20.0 + k * m.cell_m, 0))
		m.cells[c.y * m.cells_per_side + c.x] = (1 << 10) | (1 << 28) | (5 << 18)
	m._los_local = PackedFloat32Array()
	assert_bool(m.line_of_sight(Vector2(-100, 0), 3.0, Vector2(100, 0), 3.0)).is_true()
	for k in range(3, 6):
		var c := m.cell_of(Vector2(-20.0 + k * m.cell_m, 0))
		m.cells[c.y * m.cells_per_side + c.x] = (1 << 10) | (1 << 28) | (5 << 18)
	m._los_local = PackedFloat32Array()
	assert_bool(m.line_of_sight(Vector2(-100, 0), 3.0, Vector2(100, 0), 3.0)).is_false()


# --- I91: line of sight for fire -------------------------------------------------------------

func test_direct_fire_needs_line_of_sight_and_lrms_a_spotter() -> void:
	_flat_world()
	var m := world.map
	for col in range(28, 33):  # ridge between the shooters at y=0 and the target at y=150
		for row in [27, 26]:
			m.elevation_m[row * m.vertices_per_side + col] = 30.0
	var target := _target_mech(Vector2(0, 150))
	target.team = 1
	target.is_player = false
	var lrm := _vehicle("lrmcarrier", 0, Vector2(10, 20))
	assert_bool(world.line_of_sight(lrm, target)).is_false()
	assert_int(_shots_by(lrm, 15.0)).is_equal(0)  # nobody on the team sees the target
	var spotter := _vehicle("harasser", 0, Vector2(60, 150))
	spotter.awake = false  # sees, does not shoot
	assert_bool(world.team_line_of_sight(0, target)).is_true()
	assert_int(_shots_by(lrm, 15.0)).is_greater(0)  # indirect fire on the spotter's LOS


# --- I92: brain moves walk -------------------------------------------------------------------

func test_brain_moves_walk_unless_the_script_runs() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01", 1)
	var p: SimAbl.Pilot = null
	for u in sm.world.units:
		if u.team != sm.player_team and u.brain is SimAbl.Pilot:
			p = u.brain
			break
	var u := p.unit
	var goal := sm.world.map.nearest_walkable(u.position + Vector2(100, 0))
	sm.abl._issue(p, {"code": SimAbl.TO_MOVETO_POINT, "goal": goal, "run": false, "origin": 2})
	assert_bool(u.move_run).is_false()
	sm.abl._issue(p, {"code": SimAbl.TO_MOVETO_POINT, "goal": goal + Vector2(20, 0), "run": true, "origin": 2})
	assert_bool(u.move_run).is_true()
	var enemy: SimUnit = sm.world.units.filter(func(o): return o.team == sm.player_team and o.is_mover())[0]
	sm.abl._issue(p, {"code": SimAbl.TO_ATTACK_OBJECT, "target": enemy, "pursue": true, "origin": 2})
	assert_bool(u.move_run).is_true()  # an attack moves at the last move's pace
	sm.abl._issue(p, {"code": SimAbl.TO_MOVETO_POINT, "goal": goal, "run": false, "origin": 2})
	sm.abl._issue(p, {"code": SimAbl.TO_ATTACK_OBJECT, "target": enemy, "pursue": true, "origin": 2})
	assert_bool(u.move_run).is_false()
	sm.world.rules.brain_walk = false
	sm.abl._issue(p, {"code": SimAbl.TO_MOVETO_POINT, "goal": goal + Vector2(40, 0), "run": false, "origin": 2})
	assert_bool(u.move_run).is_true()


# --- F6: an engaged brain fires only at its target -----------------------------------------

func test_engaged_brain_fires_only_at_its_last_target() -> void:
	_flat_world()
	var ai := _vehicle("harasser", 1, Vector2.ZERO)
	ai.brain = RefCounted.new()
	ai.brain_name = "patrol"
	ai.brain_engaged = true
	var near := _target_mech(Vector2(0, 60))
	var other := _target_mech(Vector2(0, 40))
	assert_object(world._pick_target(ai)).is_null()  # no fire-at-will fallback
	ai.current_target = near
	assert_object(world._pick_target(ai)).is_same(near)  # not the nearer one
	near.position = Vector2(0, 300)  # beyond attackRadius (275 m): dropped
	assert_object(world._pick_target(ai)).is_null()
	assert_object(ai.current_target).is_null()
	rules.brain_target_only = false
	assert_object(world._pick_target(ai)).is_same(other)  # the old fallback
	var plain := _vehicle("harasser", 1, Vector2(5, 0))  # no brain: fires at will
	assert_object(world._pick_target(plain)).is_same(other)


# --- area-effect weapons (weaponbolt.cpp:762-794) --------------------------------------------

func _armour_sum(u: SimUnit) -> float:
	var t := 0.0
	for a in u.armor:
		t += a
	return t


func test_long_tom_shells_hit_everything_around_the_target() -> void:
	_flat_world()
	var gun := _vehicle("guardtower", 0, Vector2.ZERO, 5.0)  # gunnery 5: it misses, the blast still lands
	var a := _target_mech(Vector2(0, 120))
	a.team = 1
	var b := _target_mech(Vector2(15, 120))
	b.team = 1
	var c := _target_mech(Vector2(60, 120))  # outside the 37 m blast
	c.team = 1
	var before := [_armour_sum(a), _armour_sum(b), _armour_sum(c)]
	assert_int(_shots_by(gun, 3.0)).is_equal(1)  # recycle 7.14 s
	assert_float(_armour_sum(a)).is_less(before[0])
	assert_float(_armour_sum(b)).is_less(before[1])
	assert_float(_armour_sum(c)).is_equal(before[2])
	rules.area_effect_weapons = false
	var gun2 := _vehicle("guardtower", 0, Vector2(30, 0), 5.0)
	var b2 := _armour_sum(b)
	_shots_by(gun2, 3.0)
	assert_float(_armour_sum(b)).is_equal(b2)  # a plain miss without the blast rule


func test_an_attacker_closes_until_it_can_see_the_target() -> void:
	_flat_world()
	var m := world.map
	for col in range(28, 33):  # ridge between the attacker at y=0 and the target at y=110
		m.elevation_m[27 * m.vertices_per_side + col] = 30.0
	var target := _target_mech(Vector2(0, 110))
	target.team = 1
	var a := SimFixture.mech("atlas", rules)
	a.team = 0
	world.add_unit(a)
	world.order_attack(a, target)
	var start := a.position
	_shots_by(a, 1.0)
	assert_float(a.distance_to(target.position)).is_less_equal(world.attack_range(a) / 0.9 + 1.0)  # in reach...
	_shots_by(a, 6.0)
	assert_float(a.position.distance_to(start)).is_greater(10.0)  # ...but keeps walking for a line of fire


func test_a_unit_placed_on_a_blocked_cell_can_walk_out() -> void:
	_flat_world()
	var m := world.map
	for dy in range(-1, 2):
		for dx in range(-1, 2):
			var c := m.cell_of(Vector2.ZERO) + Vector2i(dx, dy)
			m.cells[c.y * m.cells_per_side + c.x] = 0  # impassable footprint (mc2_04's facility Anubis)
	m._astar = null
	var path := m.find_path(Vector2.ZERO, Vector2(100, 0))
	assert_bool(path.is_empty()).is_false()
	assert_bool(m.is_walkable(m.cell_of(path[0]))).is_true()


func test_an_attacker_in_reach_without_sight_moves_to_a_spot_with_it() -> void:
	_flat_world()
	var m := world.map
	var target := _target_mech(Vector2(0, 60))
	target.team = 1
	# a 12 m wall of raised (building) cells right in front of the target, toward the attacker
	for x in range(-3, 4):
		var c := m.cell_of(Vector2(x * m.cell_m, 45))
		m.cells[c.y * m.cells_per_side + c.x] = (1 << 10) | (3 << 18)
	m._los_local = PackedFloat32Array()
	var a := SimFixture.mech("atlas", rules)
	a.team = 0
	world.add_unit(a)
	assert_bool(world.line_of_sight(a, target)).is_false()
	world.order_attack(a, target)
	var seen := false
	for i in 200:
		world.step()
		world.events.clear()
		world._los_cache.clear()
		if world.line_of_sight(a, target):
			seen = true
			break
	assert_bool(seen).is_true()


# --- group goals and attack positions (group.cpp:401, mover.cpp:4364) -----------------------

func test_group_move_goals_spread_round_the_click() -> void:
	_flat_world()
	var g := Vector2(40, 40)
	var goals := world.group_move_goals(g, 5)
	assert_int(goals.size()).is_equal(5)
	assert_int(world.map.cell_of(goals[0]).x).is_equal(world.map.cell_of(g).x)  # the click itself first
	for i in range(1, 5):
		assert_float((goals[i] as Vector2).distance_to(goals[0])).is_greater(world.map.cell_m * 1.5)  # its neighbours are taken
	for i in 5:
		for j in range(i + 1, 5):
			assert_float((goals[i] as Vector2).distance_to(goals[j])).is_greater(1.0)  # one cell each


func test_a_lance_attacking_one_target_spreads_on_the_fire_ring() -> void:
	_flat_world()
	var target := _target_mech(Vector2(0, 300))
	target.team = 1
	var lance: Array = []
	for i in 4:
		var m := SimFixture.mech(["bushwacker", "shootist", "catapult", "hunchback"][i], rules)
		m.team = 0
		m.is_player = true
		m.group = 0
		m.position = Vector2(i * 4.0, 0)
		world.add_unit(m)
		lance.append(m)
		world.order_attack(m, target)
	for k in 600:
		world.step()
		world.events.clear()
	var min_sep := INF
	for i in 4:
		assert_bool(world.line_of_sight(lance[i], target)).is_true()
		assert_float(lance[i].distance_to(target.position)).is_less_equal(world.attack_range(lance[i]) / 0.9 + 12.0)
		for j in range(i + 1, 4):
			min_sep = minf(min_sep, lance[i].position.distance_to(lance[j].position))
	assert_float(min_sep).is_greater(world.map.cell_m * 0.9)  # not stacked in one file


func test_optimal_fire_range_follows_the_weapons() -> void:
	_flat_world()
	var cat := SimFixture.mech("catapult", rules)  # LRM boat
	var hb := SimFixture.mech("hunchback", rules)  # AC20
	world.add_unit(cat)
	world.add_unit(hb)
	assert_float(world.optimal_fire_range(cat)).is_greater(world.optimal_fire_range(hb))


# --- I93: turret slew and vehicle acceleration -----------------------------------------------

func test_a_turret_must_turn_before_it_fires_behind() -> void:
	_flat_world()
	rules.vehicle_weapon_nodes = false
	var p := _vehicle("partisan", 1, Vector2.ZERO)  # MaxTurretYawRate 120
	p.facing = 0.0
	_target_mech(Vector2(0, -60))  # straight behind it
	var first := -1.0
	var t := 0.0
	while t < 5.0 and first < 0.0:
		world.step()
		t += SimWorld.TICK
		for e in world.events:
			if e["type"] == "shot" and e["from"] == p.id:
				first = t
		world.events.clear()
	assert_float(first).is_greater_equal(1.3)  # (180 - 12.5) / 120 s
	assert_float(first).is_less(2.5)
	rules.slew = false
	var q := _vehicle("partisan", 1, Vector2(30, 0))
	q.facing = 0.0
	assert_int(_shots_by(q, 0.3)).is_greater(0)  # instant twist without the rule


func test_vehicles_accelerate_at_max_accel() -> void:
	_flat_world()
	var legion := _vehicle("tankk", 1, Vector2.ZERO)  # MaxAccel 0.5, 12 m/s
	world.order_move(legion, Vector2(0, 300))
	for i in 20:
		world.step()
	assert_float(legion.speed).is_less_equal(1.05)  # 2 s at 0.5 m/s2
	var h := _vehicle("harasser", 1, Vector2(50, 0))  # MaxAccel 15
	world.order_move(h, Vector2(50, 300))
	for i in 20:
		world.step()
	assert_float(h.speed).is_greater(10.0)  # MaxAccel 15: near full speed already


# --- force fire, attack point, DFA -----------------------------------------------------------

func test_attack_point_fires_one_volley_unless_suppressing() -> void:
	_flat_world()
	var gun := _vehicle("guardtower", 0, Vector2.ZERO)
	var nearby := _target_mech(Vector2(0, 110))
	nearby.team = 1
	world.order_attack_point(gun, Vector2(0, 120), true, false)
	assert_int(_shots_by(gun, 1.0)).is_equal(1)
	assert_int(gun.order).is_equal(SimWorld.Order.HOLD)  # one volley clears it
	world.order_attack_point(gun, Vector2(0, 120), true, false, true)
	var shots := 0
	var hits := 0
	for i in 200:
		world.step()
		for e in world.events:
			if e["type"] == "shot" and e["from"] == gun.id:
				shots += 1
			if e["type"] == "impact" and e["unit"] == nearby.id:
				hits += 1
		world.events.clear()
	assert_int(shots).is_greater(1)  # suppression keeps shelling the point
	assert_int(hits).is_equal(shots)  # the Long Tom's blast reaches 10 m off the point


func test_force_fire_keeps_a_friendly_target() -> void:
	_flat_world()
	var a := SimFixture.mech("atlas", rules)
	a.team = 0
	world.add_unit(a)
	var friend := _target_mech(Vector2(0, 80))
	world.order_attack(a, friend, true, false, "", true)
	assert_int(_shots_by(a, 3.0)).is_greater(0)
	var b := SimFixture.mech("atlas", rules)
	b.team = 0
	b.position = Vector2(20, 0)
	world.add_unit(b)
	world.order_attack(b, friend, true, false)  # not forced: a friend is dropped
	assert_int(_shots_by(b, 3.0)).is_equal(0)


func test_death_from_above_on_landing() -> void:
	_flat_world()
	var j := SimFixture.mech("laohu", rules) if GameData.chassis.has("laohu") else SimFixture.mech("shadowcat", rules)
	j.team = 0
	world.add_unit(j)
	var under := _target_mech(Vector2(0, 60))
	under.team = 1
	var hit_before := _armour_sum(under)
	var own_before := _armour_sum(j)
	assert_bool(world.order_jump(j, Vector2(0, 60))).is_true()
	var dfa := 0
	for i in 40:
		world.step()
		for e in world.events:
			if e["type"] == "dfa":
				dfa += 1
		world.events.clear()
	assert_int(dfa).is_equal(1)
	assert_float(hit_before - _armour_sum(under)).is_greater(0.0)
	assert_float(own_before - _armour_sum(j)).is_greater(0.0)  # the jumper's legs take it too
