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
	var old_brain = enemy.brain
	var pilots_before: int = sm.abl.pilots.size()
	assert_bool(sm.support.call_power("salvage_craft", enemy)).is_true()
	_run(10.0)
	assert_int(enemy.team).is_equal(0)
	assert_int(enemy.commander).is_equal(0)
	assert_int(enemy.status).is_equal(SimUnit.Status.NORMAL)
	assert_float(enemy.internal[SimMech.Body.CTORSO]).is_equal(enemy.max_internal[SimMech.Body.CTORSO])
	assert_float(_armour(enemy)).is_equal(armour)  # armour is not restored (3.6)
	assert_bool(enemy.brain is SimAbl.Pilot).is_true()
	# I119: the new pbrain replaces the old enemy brain in the pilot list instead of joining it
	assert_bool(old_brain is SimAbl.Pilot).is_true()
	assert_bool(enemy.brain != old_brain).is_true()
	assert_bool(sm.abl.pilots.has(old_brain)).is_false()
	assert_int(sm.abl.pilots.filter(func(p): return p.unit == enemy).size()).is_equal(1)
	assert_int(sm.abl.pilots.size()).is_equal(pilots_before)


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


# --- repair bays (3.7, I95) ------------------------------------------------------------------

func _quiet_mission(mission: String) -> SimMission:
	SimMission.use_turrets = false
	var q := SimMission.load_mission(GameData, mission, 1, false)
	SimMission.use_turrets = true
	for u in q.world.units:
		if u.is_mover() and u.team != q.player_team:
			u.exists = false  # nobody to interfere
	return q


func test_a_friendly_repair_bay_repairs_a_mech_and_burns_its_own_points() -> void:
	var q := _quiet_mission("mc2_13")
	var bays := q.world.units.filter(func(u): return u is SimStructure and u.can_refit and u.mech_bay)
	assert_int(bays.size()).is_equal(2)
	var bay: SimStructure = bays[0]
	var m: SimMech = q.world.units.filter(func(u): return u is SimMech and u.team == q.player_team)[0]
	m.position = q.world.map.nearest_walkable(bay.position + Vector2(60, 0))
	for i in m.armor.size():
		m.armor[i] = m.max_armor[i] - 4.0
	assert_bool(q.support.order_bay_repair(m, bay)).is_false()  # not ours yet: capture it first
	bay.team = q.player_team
	assert_bool(q.support.order_bay_repair(m, bay)).is_true()
	var other: SimMech = q.world.units.filter(func(u): return u is SimMech and u.team == q.player_team)[1]
	other.armor[0] -= 3.0
	assert_bool(q.support.order_bay_repair(other, bay)).is_false()  # one at a time
	var shut := false
	for i in 900:
		q.step()
		q.world.events.clear()
		shut = shut or m.status == SimUnit.Status.SHUTDOWN
		if q.support.bay_repairs.is_empty():
			break
	assert_bool(shut).is_true()  # powered down on the bay
	assert_bool(SimSupport.needs_refit(m)).is_false()
	assert_int(m.status).is_equal(SimUnit.Status.NORMAL)
	assert_float(bay.damage).is_equal_approx(4.0 * m.armor.size(), 1.0)  # the points used are the bay's damage
	assert_object(bay.refit_buddy).is_null()


# --- artillery piece, minelayer, mines (3.5, 3.9, I96) ---------------------------------------

func test_artillery_piece_and_minelayer_are_delivered() -> void:
	sm.support.rp = 20000
	var m: SimUnit = _lance()[0]
	assert_bool(sm.support.call_power("artillery_piece", m.position + Vector2(40, 0))).is_true()
	assert_int(sm.support.rp).is_equal(12000)
	_run(11.0)
	var guns := sm.world.units.filter(func(u): return u is SimVehicle and u.model == "artillerypiece")
	assert_int(guns.size()).is_equal(1)
	assert_int(guns[0].team).is_equal(sm.player_team)
	assert_float(guns[0].run_speed).is_equal(0.0)  # immobile
	assert_float(guns[0].los_factor).is_equal(1.2)
	assert_bool(sm.support.call_power("minelayer", m.position + Vector2(-40, 0))).is_true()
	_run(11.0)
	var layers := sm.world.units.filter(func(u): return u is SimVehicle and u.mine_stock > 0)
	assert_int(layers.size()).is_equal(1)
	assert_int(layers[0].mine_stock).is_equal(160)


func test_minelayer_lays_mines_that_heavy_units_set_off() -> void:
	var q := _quiet_mission("mc2_02")
	var w := q.world
	var ml := SimVehicle.from_data(JSON.parse_string(FileAccess.get_file_as_string("res://data/vehicles/minelayer.json")), w.rules, SimPilot.make(50, 50))
	ml.team = q.player_team
	var lance := w.units.filter(func(u): return u is SimMech and u.team == q.player_team)
	ml.position = w.map.nearest_walkable(lance[0].position + Vector2(0, 40))
	w.add_unit(ml)
	var goal := w.map.nearest_walkable(ml.position + Vector2(80, 0))
	assert_bool(q.support.order_lay_mines(ml, goal)).is_true()
	var laid := 0
	for i in 200:
		q.step()
		for e in w.events:
			if e["type"] == "mine_laid":
				laid += 1
		w.events.clear()
	assert_int(laid).is_greater(3)
	assert_int(ml.mine_stock).is_equal(160 - laid)
	assert_float(ml.armor[SimVehicle.Section.TURRET]).is_equal(160.0 - laid)
	# a heavy mech steps on one: 12 damage, the mine is spent; a light one doesn't set it off
	var cell := Vector2i(-1, -1)
	for c in w.map.mines.size():
		if w.map.mines[c] == 1:
			cell = Vector2i(c % w.map.cells_per_side, c / w.map.cells_per_side)
			break
	var heavy := SimFixture.mech("atlas", w.rules)
	heavy.team = q.player_team
	heavy.awake = false
	w.add_unit(heavy)
	var light := SimFixture.mech("raven", w.rules)
	light.team = 1
	w.add_unit(light)
	light.position = w.map.cell_center(cell)
	w.step()
	assert_int(w.map.mine_at(cell)).is_equal(1)  # 35 t: too light
	light.position = Vector2(9999, 9999)
	var before := 0.0
	for a in heavy.armor + heavy.internal:
		before += a
	heavy.position = w.map.cell_center(cell)
	w.step()
	var after := 0.0
	for a in heavy.armor + heavy.internal:
		after += a
	assert_int(w.map.mine_at(cell)).is_equal(2)
	assert_float(before - after).is_equal_approx(12.0, 0.01)



func test_a_mech_stays_powered_down_through_the_truck_repair() -> void:
	# I100: the heat restart (H7) used to power it straight back up
	sm.support.rp = 20000
	var m: SimMech = _lance()[0]
	for i in m.armor.size():
		m.armor[i] = m.max_armor[i] * 0.3
	sm.support.call_power("repair_truck", m.position + Vector2(30, 0))
	_run(5.0)
	var truck: SimUnit = sm.world.units.filter(func(u): return u.refit_pool > 0.0 and u.team == 0)[0]
	sm.support.order_repair(truck, m)
	var shut := 0
	var up_during := 0
	for i in 300:
		sm.step()
		sm.world.events.clear()
		if sm.support.repairs.any(func(r): return r["mech"] == m and r["phase"] == "refit"):
			if m.status == SimUnit.Status.SHUTDOWN:
				shut += 1
			else:
				up_during += 1
		if sm.support.repairs.is_empty() and shut > 0:
			break
	assert_int(shut).is_greater(0)
	assert_int(up_during).is_equal(0)
	assert_int(m.status).is_equal(SimUnit.Status.NORMAL)  # powered back up when done
	assert_bool(m.powered_down).is_false()


# --- scout copter and air movers (3.8) --------------------------------------------------------

func test_scout_copter_is_delivered_shut_down_and_flies() -> void:
	sm.support.rp = 20000
	var m: SimUnit = _lance()[0]
	assert_bool(sm.support.call_power("scout_copter", m.position + Vector2(30, 0))).is_true()
	assert_int(sm.support.rp).is_equal(18000)
	_run(5.0)
	var cop: Array = sm.world.units.filter(func(u): return u is SimMech and u.model == "scoutcopter")
	assert_int(cop.size()).is_equal(1)
	var c: SimMech = cop[0]
	assert_bool(c.flying).is_true()
	assert_int(c.status).is_equal(SimUnit.Status.SHUTDOWN)  # created shut down
	_run(6.0)
	assert_int(c.status).is_equal(SimUnit.Status.NORMAL)  # up as the VTOL leaves
	assert_float(c.los_factor).is_equal(1.2)
	# flies straight: a path is the goal itself, whatever lies between
	var far := c.position + Vector2(600, 0)
	assert_bool(sm.world.order_move(c, far)).is_true()
	assert_int(c.path.size()).is_equal(1)


func test_air_movers_ignore_strikes_and_cannot_capture() -> void:
	sm.support.rp = 20000
	var m: SimUnit = _lance()[0]
	sm.support.call_power("scout_copter", m.position + Vector2(30, 0))
	_run(11.0)
	var c: SimMech = sm.world.units.filter(func(u): return u is SimMech and u.model == "scoutcopter")[0]
	var before := _armour(c)
	sm.support.call_power("air_strike", c.position)
	_run(8.0)
	assert_float(_armour(c)).is_equal(before)  # immune in flight (artlry.cpp:585-592)
	var building: SimUnit = sm.world.units.filter(func(u): return u is SimStructure and sm.abl.can_capture(u, 0))[0]
	sm.abl.player_order(c, "capture", building)
	assert_int(int(c.brain.order.get("code", 0))).is_not_equal(SimAbl.TO_CAPTURE)


## The aerospace spotter (gvehicl.cpp:3640-3664) strikes its pilot's current target, not the nearest
## player unit. The target must be within 120 m and in sight while a 10 s timer runs, and the timer is
## kept while the target is away. I114.
func test_the_spotter_strikes_its_own_target_after_ten_seconds_in_range() -> void:
	var q := _quiet_mission("mc2_19")
	var spot: SimUnit = q.world.units.filter(func(u): return u is SimVehicle and u.model == "aerospotter")[0]
	spot.exists = true
	spot.awake = false  # no brain or gunnery of its own to change its target
	var lance: Array = q.world.units.filter(func(u): return u is SimMech and u.team == 0 and u.commander == 0)
	var target: SimUnit = lance[0]
	var other: SimUnit = lance[1]
	q.world.rules.line_of_sight = false  # sight is tested separately (SimWorld.line_of_sight)
	other.position = spot.position + Vector2(30, 0)  # nearer, but not its target
	target.position = spot.position + Vector2(0, 90)
	spot.current_target = target
	var strikes := func() -> Array: return q.support.pending.filter(func(p): return p["kind"] == "strike")
	for i in int(6.0 / SimWorld.TICK):
		q.step()
	target.position = spot.position + Vector2(0, 200)  # out of range: the timer holds
	for i in int(5.0 / SimWorld.TICK):
		q.step()
	assert_int(strikes.call().size()).is_equal(0)
	target.position = spot.position + Vector2(0, 90)
	for i in int(4.5 / SimWorld.TICK):
		q.step()
	var s: Array = strikes.call()
	assert_int(s.size()).is_equal(1)
	assert_float((s[0]["at"] as Vector2).distance_to(target.position)).is_less(1.0)


## A destroyed building with an ExplosionDamage blows up (bldng.cpp:205-211, 1476-1488). mc2_13's
## large fuel tanks (30 damage, 300 wu = 60 m) are the guides' answer to the Thor and Ryoken.
func test_a_destroyed_fuel_tank_blows_up_on_whoever_is_near() -> void:
	var q := _quiet_mission("mc2_13")
	var tank: SimStructure = q.world.units.filter(func(u): return u is SimStructure and u.name == "LargeFuelTank")[0]
	assert_float(tank.explosion_damage).is_equal(30.0)
	assert_float(tank.explosion_radius_m).is_equal_approx(60.0, 0.01)
	tank.position = Vector2(-1100.0, -200.0)  # away from the depot's other tanks and pipes (they would chain)
	var m: SimUnit = q.world.units.filter(func(u): return u is SimMech and u.team == 0)[0]
	m.position = tank.position + Vector2(25, 0)
	var far: SimUnit = q.world.units.filter(func(u): return u is SimMech and u.team == 0)[1]
	far.position = tank.position + Vector2(90, 0)
	var before: float = _armour(m) + m.internal.reduce(func(a, b): return a + b, 0.0)
	var far_before := _armour(far)
	tank.take_hit(q.world.rules, q.world.rng, tank.damage_level + 1.0, 0, 143, 0.0)
	var blasts := 0
	for i in 3:
		q.step()
		for e in q.world.events:
			if e["type"] == "impact" and e["unit"] == m.id and e.get("form", "") == "blast":
				blasts += 1
		q.world.events.clear()
	assert_int(blasts).is_equal(6)  # 30 damage in chunks of 5 (carnage.cpp:349-367)
	assert_float(_armour(m) + m.internal.reduce(func(a, b): return a + b, 0.0)).is_less_equal(before - 29.0)
	assert_float(_armour(far)).is_equal(far_before)


## A turret control whose generator is destroyed goes to sleep with its turrets, and a sleeping
## building can't be captured (bldng.cpp:903-913, 1046; turret.cpp:620-633).
func test_a_control_without_its_generator_sleeps_and_cannot_be_taken() -> void:
	var q := SimMission.load_mission(GameData, "mc2_22", 1)
	var ctl: SimStructure = null
	for u in q.world.units:
		if u is SimTurret and u.parent != null and u.parent.parent != null:
			ctl = u.parent
			break
	assert_object(ctl).is_not_null()
	assert_bool(q.abl.can_capture(ctl, 0)).is_true()
	var gen: SimStructure = ctl.parent
	gen.take_hit(q.world.rules, q.world.rng, gen.damage_level + 1.0, 0, 143, 0.0)
	for i in 3:
		q.step()
	assert_bool(ctl.awake).is_false()
	var turrets := q.world.units.filter(func(u): return u is SimTurret and u.parent == ctl)
	assert_bool(not turrets.is_empty() and turrets.all(func(t): return not t.active)).is_true()
	assert_bool(q.abl.can_capture(ctl, 0)).is_false()
