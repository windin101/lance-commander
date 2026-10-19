extends GdUnitTestSuite
## Support powers (docs/specs/support-powers.md): Resource Points, air strike, repair
## truck, salvage craft, sensor probe, RP from captures.

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_02", 1)


func _run(seconds: float) -> void:
	for i in int(seconds / SimWorld.TICK):
		sm.step()
		sm.world.events.clear()


func _lance() -> Array:
	return sm.world.units.filter(func(u): return u is SimMech and u.team == 0 and u.commander == 0)


func _armour(u: SimUnit) -> float:
	var t := 0.0
	for a in u.armor:
		t += a
	return t


func test_resource_points_start_from_the_mission() -> void:
	assert_int(sm.support.rp).is_equal(int(sm.fit["MissionSettings"]["ResourcePoints"]))
	sm.support.rp = 6999
	assert_bool(sm.support.can_call("air_strike")).is_false()
	assert_bool(sm.support.can_call("sensor_probe")).is_true()


func test_air_strike_lands_after_seven_seconds_and_hurts_everyone_in_reach() -> void:
	sm.support.rp = 20000
	var m: SimUnit = _lance()[0]
	var before := _armour(m)
	assert_bool(sm.support.call_power("air_strike", m.position + Vector2(10, 0))).is_true()
	assert_int(sm.support.rp).is_equal(13000)
	_run(6.5)
	assert_float(_armour(m)).is_equal(before)
	_run(1.0)
	assert_float(_armour(m)).is_less(before)  # friendly fire: no team check (3.1)


func test_repair_truck_is_delivered_and_repairs_a_mech() -> void:
	sm.support.rp = 20000
	var m: SimMech = _lance()[0]
	for i in m.armor.size():
		m.armor[i] = m.max_armor[i] * 0.5
	var before := _armour(m)
	sm.support.call_power("repair_truck", m.position + Vector2(30, 0))
	assert_bool(sm.support.can_call("salvage_craft")).is_false()  # one delivery at a time
	_run(5.0)
	var trucks := sm.world.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0)
	assert_int(trucks.size()).is_equal(1)
	var truck: SimUnit = trucks[0]
	assert_bool(sm.support.order_repair(truck, m)).is_true()
	_run(12.0)
	assert_float(_armour(m)).is_greater(before + 50.0)
	assert_float(truck.refit_pool).is_less(500.0)


func test_salvage_craft_takes_a_disabled_enemy_mech() -> void:
	sm.support.rp = 20000
	var enemy: SimMech = sm.world.units.filter(func(u): return u is SimMech and u.team != 0)[0]
	enemy.status = SimUnit.Status.DISABLED
	enemy.internal[SimMech.Body.CTORSO] = 0.0
	var armour := _armour(enemy)
	assert_bool(sm.support.call_power("salvage_craft", enemy)).is_true()
	_run(10.0)
	assert_int(enemy.team).is_equal(0)
	assert_int(enemy.commander).is_equal(0)
	assert_int(enemy.status).is_equal(SimUnit.Status.NORMAL)
	assert_float(enemy.internal[SimMech.Body.CTORSO]).is_equal(enemy.max_internal[SimMech.Body.CTORSO])
	assert_float(_armour(enemy)).is_equal(armour)  # armour is not restored (3.6)
	assert_bool(enemy.brain is SimAbl.Pilot).is_true()


func test_capturing_the_resource_building_pays_rp() -> void:
	var t: SimUnit = sm.objectives.objectives[0]["conditions"][0]["unit"]
	assert_int(t.resource_points).is_equal(10000)
	var rp := sm.support.rp
	sm.abl.capture(_lance()[0], t)
	assert_int(sm.support.rp).is_equal(rp + 10000)


func test_sensor_probe_reveals_far_enemies() -> void:
	sm.support.rp = 20000
	var far: SimUnit = null
	for u in sm.world.units:
		if u.is_mover() and u.team != 0 and not sm.abl.is_contact(0, u):
			far = u
			break
	assert_object(far).is_not_null()
	sm.support.call_power("sensor_probe", far.position)
	assert_bool(sm.abl.is_contact(0, far)).is_true()
