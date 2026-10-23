extends GdUnitTestSuite
## Capture (docs/specs/capture-and-objectives.md part A) on mc2_02's first objective,
## "Capture Resource Building": instant on arrival, blocked by an armed enemy nearby,
## completes the capture objective.

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_02", 1)


func _target() -> SimUnit:
	return sm.objectives.objectives[0]["conditions"][0]["unit"]


func _mech() -> SimUnit:
	return sm.world.units.filter(func(u): return u is SimMech and u.team == 0 and u.commander == 0)[0]


func _clear(around: Vector2, radius: float) -> void:
	for u in sm.world.units:
		if u.is_mover() and u.team != 0 and u.position.distance_to(around) <= radius:
			u.status = SimUnit.Status.DESTROYED


func _run(seconds: float) -> void:
	for i in int(seconds / SimWorld.TICK):
		sm.step()


func test_target_is_capturable_and_capture_completes_the_objective() -> void:
	var t := _target()
	assert_object(t).is_not_null()
	assert_bool(t is SimStructure).is_true()
	assert_bool(t.capturable).is_true()
	assert_bool(sm.abl.can_capture(t, 0)).is_true()
	_clear(t.position, 400.0)
	var m := _mech()
	m.position = sm.world.map.nearest_walkable(t.position + Vector2(0, -60))
	sm.abl.player_order(m, "capture", t)
	assert_int(m.brain.order["code"]).is_equal(SimAbl.TO_CAPTURE)
	_run(20.0)
	assert_int(t.team).is_equal(0)
	assert_bool(sm.objectives.objectives[0]["complete"]).is_true()


func test_an_armed_enemy_near_the_target_blocks_capture() -> void:
	var t := _target()
	_clear(t.position, 400.0)
	var m := _mech()
	m.position = sm.world.map.nearest_walkable(t.position + Vector2(0, -60))
	var guard: SimUnit = sm.world.units.filter(func(u): return u.is_mover() and u.team != 0 and u.num_weapons > 0 and not u.is_disabled())[0]
	guard.position = t.position + Vector2(40, 0)
	guard.awake = true
	assert_object(sm.abl.capture_blocker(t, m, true)).is_same(guard)
	m.brain.order = {"code": SimAbl.TO_CAPTURE, "target": t, "goal": m.position, "origin": 0}
	m.position = t.position + Vector2(0, -20)
	sm.abl._order_progress(m.brain, m)
	assert_int(t.team).is_not_equal(0)
	assert_int(m.brain.order["code"]).is_equal(SimAbl.TO_NONE)


func test_captured_vehicle_becomes_a_hulk() -> void:
	var v: SimUnit = sm.world.units.filter(func(u): return u is SimVehicle and u.team != 0)[0]
	v.capturable = true
	sm.abl.capture(_mech(), v)
	assert_int(v.team).is_equal(0)
	assert_bool(v.hulk).is_true()
	assert_bool(v.awake).is_false()
	assert_bool(sm.abl.can_capture(v, 0)).is_false()


func test_a_capture_walk_ends_inside_reach_of_a_big_building() -> void:
	# I85: mc2_13's Weapons Facility #3, whose footprint keeps a mech 30+ m from its centre
	var q := SimMission.load_mission(GameData, "mc2_13", 1)
	var fac := q.structure_near(Vector2(-2240.0, -5354.666504))
	var m: SimUnit = q.world.units.filter(func(u): return u is SimMech and u.team == q.player_team)[0]
	for u in q.world.units:
		if u.is_mover() and u.team != q.player_team:
			u.exists = false
	for dir in [Vector2(0, 1), Vector2(1, 0), Vector2(0, -1), Vector2(-1, 0)]:
		fac.team = -1
		m.position = q.world.map.nearest_walkable(fac.position + dir * 150.0)
		q.world.order_hold(m)
		q.abl.player_order(m, "capture", fac, {"run": true})
		var goal: Vector2 = m.brain.order["goal"]
		assert_float(goal.distance_to(fac.position)).is_less_equal(SimAbl.CAPTURE_M + fac.extent_m - SimWorld.ARRIVE_M)
		var t0 := q.world.time
		while q.world.time - t0 < 40.0 and fac.team != q.player_team:
			q.step()
			q.world.events.clear()
		assert_int(fac.team).is_equal(q.player_team)
