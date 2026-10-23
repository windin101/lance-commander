extends GdUnitTestSuite
## Map turrets and their control buildings (I94, turret.cpp), on a flat test map and on the
## converted missions.

var rules: SimRules
var world: SimWorld


func before_test() -> void:
	rules = SimFixture.rules()
	world = SimWorld.new(rules, SimFixture.flat_map(), 1)


func _turret_type(weapons := [101, 101, -1, -1]) -> Dictionary:
	return {"name": "MediumAutoCannonTurret", "appearance": "mediumautocannonturret", "class": 21,
		"turret": {"damage_level": 25, "weapons": weapons, "pilot_skill": 50, "attack_radius": 500.0, "yaw_rate": 20.0,
			"los_factor": 1.0, "little_extent": 35, "explosion_damage": 0.0, "explosion_radius": 0.0, "tonnage": 20}}


func _control(team: int, at: Vector2) -> SimStructure:
	var c := SimStructure.new()
	c.name = "TurretControl"
	c.damage_level = 55.0
	c.extent_m = 7.0
	c.team = team
	c.position = at
	c.control = true
	c.capturable = true
	world.add_unit(c)
	return c


func _turret(team: int, at: Vector2, parent: SimStructure = null) -> SimTurret:
	var t := SimTurret.from_type(_turret_type(), rules)
	t.team = team
	t.position = at
	t.parent = parent
	world.add_unit(t)
	return t


func _mech(team: int, at: Vector2) -> SimMech:
	var m := SimFixture.mech("atlas", rules)
	m.team = team
	m.is_player = team == 0
	m.position = at
	m.awake = false  # a passive target
	world.add_unit(m)
	return m


func _run(seconds: float) -> Array:
	var shots: Array = []
	for i in int(seconds / SimWorld.TICK):
		world.step()
		for e in world.events:
			if e["type"] == "shot":
				shots.append(e)
		world.events.clear()
	return shots


func test_turret_turns_to_the_nearest_enemy_and_fires() -> void:
	var t := _turret(1, Vector2.ZERO)
	t.turret_yaw = 180.0  # facing south
	var far := _mech(0, Vector2(0, 90))
	var near := _mech(0, Vector2(0, 50))
	var shots := _run(4.0)
	assert_object(t.gun_target).is_same(near)
	assert_array(shots).is_empty()  # 170 degrees at 20 deg/s: still turning
	shots = _run(8.0)
	assert_float(absf(wrapf(t.turret_yaw, -180.0, 180.0))).is_less_equal(10.0)
	assert_array(shots).is_not_empty()
	assert_int(shots[0]["from"]).is_equal(t.id)
	assert_int(shots[0]["to"]).is_equal(near.id)
	assert_object(far).is_not_null()


func test_turret_ignores_movers_outside_its_attack_radius() -> void:
	var t := _turret(1, Vector2.ZERO)
	_mech(0, Vector2(0, 150))  # attack radius 500 wu = 100 m
	_run(3.0)
	assert_object(t.gun_target).is_null()


func test_turret_to_hit_is_its_skill_plus_50_against_a_still_target() -> void:
	var t := _turret(1, Vector2.ZERO)
	var m := _mech(0, Vector2(0, 50))
	assert_float(t.turret_attack_chance(rules, 0, m)).is_equal(100.0)
	m.speed = 5.0
	assert_float(t.turret_attack_chance(rules, 0, m)).is_equal(50.0)
	m.position = Vector2(0, 200)  # beyond the AC5's medium range (120 m)
	assert_float(t.turret_attack_chance(rules, 0, m)).is_equal(-1.0)


func test_capturing_the_control_turns_its_turrets() -> void:
	var c := _control(1, Vector2(200, 0))
	var t := _turret(1, Vector2.ZERO, c)
	var m := _mech(0, Vector2(0, 50))
	world.step()
	assert_object(t.gun_target).is_same(m)
	c.team = 0  # captured by the player
	world.step()
	assert_int(t.team).is_equal(0)
	assert_object(t.gun_target).is_null()
	var enemy := _mech(1, Vector2(-40, 0))
	_run(0.6)  # the next look round (SCAN_PERIOD)
	assert_object(t.gun_target).is_same(enemy)


func test_destroying_the_control_shuts_its_turrets_down_for_good() -> void:
	var c := _control(1, Vector2(200, 0))
	var t := _turret(1, Vector2.ZERO, c)
	_mech(0, Vector2(0, 50))
	world.step()
	c.status = SimUnit.Status.DESTROYED
	world.step()
	assert_bool(t.active).is_false()
	assert_array(_run(10.0)).is_empty()


func test_turret_needs_line_of_sight() -> void:
	var t := _turret(1, Vector2.ZERO)
	var m := _mech(0, Vector2(0, 60))
	var map := world.map
	for col in range(28, 33):  # a 20 m wall of ground between them, 25 m north
		map.elevation_m[29 * map.vertices_per_side + col] = 20.0
	t.turret_yaw = 0.0
	assert_bool(world.line_of_sight(t, m)).is_false()
	assert_array(_run(5.0)).is_empty()


func test_missions_load_turrets_linked_to_capturable_controls() -> void:
	for mission in ["mc2_13", "mc2_22"]:
		var sm := SimMission.load_mission(GameData, mission, 1, false)
		var turrets := sm.world.units.filter(func(u): return u is SimTurret)
		assert_int(turrets.size()).is_greater(10)
		var linked := turrets.filter(func(u): return u.parent != null)
		assert_int(linked.size()).is_greater(0)
		for t in linked:
			assert_bool(t.parent.control).is_true()
			assert_bool(t.parent.capturable).is_true()  # Liao controls ship Capturable = FALSE (I94)
		assert_int(turrets.filter(func(u): return u.num_weapons > 0).size()).is_greater(0)
	SimMission.use_turrets = false
	var quiet := SimMission.load_mission(GameData, "mc2_13", 1, false)
	SimMission.use_turrets = true
	assert_int(quiet.world.units.filter(func(u): return u is SimTurret).size()).is_equal(0)


func test_capturing_a_control_hands_the_team_to_its_own_parent() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_13", 1)
	var controls := sm.world.units.filter(func(u): return u is SimStructure and u.control and u.parent != null)
	var w := sm.world
	var c: SimStructure = controls[0] if not controls.is_empty() else null
	if c == null:  # no control with its own parent on this map: link one by hand
		c = sm.world.units.filter(func(u): return u is SimStructure and u.control)[0]
		var gen := SimStructure.new()
		gen.team = c.team
		gen.damage_level = 30.0
		w.add_unit(gen)
		c.parent = gen
	var m: SimUnit = w.units.filter(func(u): return u is SimMech and u.team == sm.player_team)[0]
	sm.abl.capture(m, c)  # Building::setTeamId passes the team up (bldng.cpp:972-979)
	assert_int(c.team).is_equal(sm.player_team)
	assert_int(c.parent.team).is_equal(sm.player_team)
	w.step()
	assert_int(c.team).is_equal(sm.player_team)  # it stays: the parent no longer pulls it back


func test_a_captured_target_is_no_longer_shot_at() -> void:
	var c := _control(1, Vector2(200, 0))
	var t := _turret(1, Vector2(0, 60), c)
	var m := SimFixture.mech("atlas", rules)
	m.team = 0
	m.is_player = true
	world.add_unit(m)
	world.order_attack(m, t)
	world.step()
	c.team = 0
	_run(2.0)  # the turret follows its control onto our side
	assert_int(t.team).is_equal(0)
	assert_array(_run(5.0).filter(func(e): return e["from"] == m.id)).is_empty()
	assert_int(m.order).is_not_equal(SimWorld.Order.ATTACK)
