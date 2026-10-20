extends GdUnitTestSuite
## SimWorld on mc2_01: spawning, movement orders, attacks, determinism.

func _mission(seed_value: int = 1) -> SimMission:
	return SimMission.load_mission(GameData, "mc2_01", seed_value)


func _team(w: SimWorld, team: int) -> Array[SimMech]:
	var out: Array[SimMech] = []
	for m in w.units:
		if m.team == team:
			out.append(m)
	return out


func test_spawns_mechs_and_lists_skipped_parts() -> void:
	var sm := _mission()
	assert_int(sm.world.units.filter(func(u): return u is SimMech).size()).is_equal(6)
	assert_int(_team(sm.world, 0).size()).is_equal(3)
	assert_int(sm.skipped.size()).is_equal(0)
	var vehicles := sm.world.units.filter(func(u): return u is SimVehicle)
	assert_int(vehicles.size()).is_equal(23)  # 4 Centipede, 4 Harasser, 7 LRMC, 8 infantry
	assert_int(vehicles.filter(func(u): return u.hover).size()).is_equal(8)
	var ww := sm.world.units[0]
	assert_str(ww.name).is_equal("Werewolf")
	assert_bool(ww.is_player).is_true()
	assert_float(ww.position.x).is_equal_approx(499.2, 0.01)
	assert_float(ww.walk_speed).is_greater(0.0)
	for m in sm.world.units:
		if m is SimMech:
			assert_bool(sm.world.map.is_walkable(sm.world.map.cell_of(m.position))).is_true()


func test_hangar_is_a_destructible_structure() -> void:
	var sm := _mission()
	var hangar := sm.structure_near(Vector2(3221.333, -277.333))
	assert_object(hangar).is_not_null()
	assert_str(hangar.name).is_equal("Hangar")
	assert_float(hangar.damage_level).is_equal(20.0)
	var w := sm.world
	var shot := {"hit": true, "damage": 12.0, "location": 0, "master_id": 143}
	SimCombat.apply_shot(w.rules, w.rng, hangar, shot, 0.0)
	assert_bool(hangar.is_destroyed()).is_false()
	SimCombat.apply_shot(w.rules, w.rng, hangar, shot, 0.0)
	assert_bool(hangar.is_destroyed()).is_true()
	# non-movers are always hit when in range
	var bw := w.units[1]
	hangar.status = SimUnit.Status.NORMAL
	bw.position = hangar.position + Vector2(0, -60)
	assert_float(SimCombat.attack_chance(w.rules, bw, bw.weapon_indices()[0], hangar)).is_equal(100.0)


func test_move_order_arrives() -> void:
	var w := _mission().world
	var m := w.units[0]
	var goal := w.map.nearest_walkable(m.position + Vector2(-150, 120))
	assert_bool(w.order_move(m, goal)).is_true()
	var t := 0.0
	while m.order == SimWorld.Order.MOVE and t < 60.0:
		w.step()
		t += SimWorld.TICK
	assert_float(m.position.distance_to(goal)).is_less(SimWorld.ARRIVE_M + 1.0)
	assert_int(m.body_state).is_equal(SimMech.BodyState.STANDING)


func test_running_speed_and_heat_from_movement() -> void:
	var w := _mission().world
	var m := w.units[1]  # Bushwacker, run 23 m/s
	w.order_move(m, w.map.nearest_walkable(m.position + Vector2(-300, 0)))
	for i in 30:
		w.step()
	assert_float(m.speed).is_greater(15.0)
	assert_int(m.body_state).is_equal(SimMech.BodyState.RUNNING)


func test_attack_order_closes_and_damages() -> void:
	var w := _mission(7).world
	var attacker := w.units[1]
	var target: SimMech = null
	for m in w.units:
		if m.name == "Urbanmech":
			target = m
			break
	assert_object(target).is_not_null()
	# Stage the duel nearby: the long route passes the guarded patrol base,
	# whose AI would (correctly) intercept a lone mech.
	target.position = w.map.nearest_walkable(attacker.position + Vector2(-60, 140))
	target.prev_position = target.position
	var armor_before := 0.0
	for a in target.armor:
		armor_before += a
	w.order_attack(attacker, target)
	var t := 0.0
	var shots := 0
	while t < 120.0 and not target.is_disabled():
		w.step()
		t += SimWorld.TICK
		for e in w.events:
			if e["type"] == "shot" and e["from"] == attacker.id:
				shots += 1
		w.events.clear()
	var armor_after := 0.0
	for a in target.armor:
		armor_after += a
	assert_int(shots).is_greater(0)
	assert_bool(armor_after < armor_before or target.is_disabled()).is_true()


func test_same_seed_same_battle() -> void:
	var a := _mission(3).world
	var b := _mission(3).world
	for w in [a, b]:
		w.order_attack(w.units[1], w.units[5])
		w.order_attack(w.units[2], w.units[5])
		for i in 600:
			w.step()
	for i in a.units.size():
		assert_object(a.units[i].position).is_equal(b.units[i].position)
		assert_object(a.units[i].armor).is_equal(b.units[i].armor)


func test_turns_to_engage_target_behind() -> void:
	var w := _mission(5).world
	var a := w.units[1]
	var t: SimMech = null
	for m in w.units:
		if m.name == "Starslayer":
			t = m
	t.position = w.map.nearest_walkable(a.position + Vector2(0, -90))
	a.facing = 0.0  # facing north, target due south: outside the fire arc
	w.order_attack(a, t)
	var shots := 0
	for i in 60:
		w.step()
		for e in w.events:
			if e["type"] == "shot" and e["from"] == a.id:
				shots += 1
		w.events.clear()
	assert_float(absf(a.rel_facing_to(t.position))).is_less_equal(w.fire_arc(a))
	assert_int(shots).is_greater(0)


# --- I82: run / walk, jump, guard, fire from position, hold position, stop ---------------

func test_walk_order_moves_at_walk_speed() -> void:
	var w := _mission().world
	var m := w.units[1]  # Bushwacker
	w.order_move(m, w.map.nearest_walkable(m.position + Vector2(-300, 0)), false)
	for i in 30:
		w.step()
	assert_float(m.speed).is_less_equal(m.walk_speed + 0.01)
	assert_float(m.speed).is_greater(m.walk_speed * 0.8)
	assert_int(m.body_state).is_equal(SimMech.BodyState.WALKING)


func test_jump_flies_to_the_point_and_lands() -> void:
	var w := _mission().world
	var m := w.units[0]  # Werewolf (Razorback Prime): jump jets
	assert_bool(m.can_jump()).is_true()
	assert_float(m.jump_range()).is_equal_approx(128.0, 0.01)  # 5 jets x 128 wu
	var goal := w.map.nearest_walkable(m.position + Vector2(0, 100))
	assert_bool(w.order_jump(m, goal)).is_true()
	var top := 0.0
	var states := {}
	for i in int(SimWorld.JUMP_TIME / SimWorld.TICK) + 2:
		w.step()
		top = maxf(top, m.jump_alt)
		states[m.body_state] = true
	assert_float(m.position.distance_to(goal)).is_less(0.01)
	assert_int(m.order).is_equal(SimWorld.Order.HOLD)
	assert_float(m.jump_alt).is_equal(0.0)
	assert_float(top).is_greater(10.0)
	assert_bool(states.has(SimUnit.BodyState.JUMPING)).is_true()


func test_jump_refused_out_of_range_impassable_or_without_jets() -> void:
	var w := _mission().world
	var ww := w.units[0]
	var bw := w.units[1]  # Bushwacker: no jump jets
	assert_bool(bw.can_jump()).is_false()
	assert_str(w.jump_refusal(bw, bw.position + Vector2(0, 50))).is_equal("no_jump_jets")
	assert_str(w.jump_refusal(ww, ww.position + Vector2(0, 200))).is_equal("out_of_range")
	var veh: SimUnit = w.units.filter(func(u): return u is SimVehicle)[0]
	assert_bool(w.order_jump(veh, veh.position + Vector2(0, 20))).is_false()
	assert_bool(w.order_jump(ww, ww.position + Vector2(0, 200))).is_false()
	assert_int(ww.order).is_equal(SimWorld.Order.HOLD)


func test_order_in_the_air_waits_for_landing() -> void:
	var w := _mission().world
	var m := w.units[0]
	var goal := w.map.nearest_walkable(m.position + Vector2(0, 100))
	w.order_jump(m, goal)
	w.step()
	var next := w.map.nearest_walkable(goal + Vector2(80, 0))
	w.order_move(m, next, true)
	assert_int(m.order).is_equal(SimWorld.Order.JUMP)
	for i in int(SimWorld.JUMP_TIME / SimWorld.TICK) + 2:
		w.step()
	assert_int(m.order).is_equal(SimWorld.Order.MOVE)


func test_fire_from_position_never_moves() -> void:
	var w := _mission().world
	var m := w.units[1]
	m.brain = null  # the world's own rules, no pbrain
	var enemy: SimUnit = _enemy_mech(w)
	enemy.position = w.map.nearest_walkable(m.position + Vector2(0, 600))
	enemy.awake = false
	var start := m.position
	w.order_attack(m, enemy, true, false)
	for i in 40:
		w.step()
	assert_float(m.position.distance_to(start)).is_less(0.5)
	assert_int(m.order).is_equal(SimWorld.Order.ATTACK)
	assert_object(m.order_target).is_same(enemy)


func test_hold_position_stays_on_attack_but_moves_on_move() -> void:
	var w := _mission().world
	var m := w.units[1]
	m.brain = null  # the world's own rules, no pbrain
	var enemy: SimUnit = _enemy_mech(w)
	enemy.position = w.map.nearest_walkable(m.position + Vector2(0, 600))
	enemy.awake = false
	m.hold_position = true
	var start := m.position
	w.order_attack(m, enemy)
	for i in 30:
		w.step()
	assert_float(m.position.distance_to(start)).is_less(0.5)
	w.order_move(m, w.map.nearest_walkable(m.position + Vector2(-200, 0)), true)
	for i in 30:
		w.step()
	assert_float(m.position.distance_to(start)).is_greater(20.0)


func test_guard_point_engages_intruder_and_returns() -> void:
	var w := _mission().world
	var m := w.units[1]
	m.brain = null  # the world's own rules, no pbrain
	var enemy: SimUnit = _enemy_mech(w)
	var post := m.position
	enemy.position = w.map.nearest_walkable(post + Vector2(0, 600))  # outside the guard radius
	enemy.awake = false
	w.order_guard(m, post)
	for i in 20:
		w.step()
	assert_object(m.order_target).is_null()
	assert_float(m.position.distance_to(post)).is_less(15.0)
	enemy.position = w.map.nearest_walkable(post + Vector2(0, 220))  # comes within 250 m
	for i in 5:
		w.step()
	assert_object(m.order_target).is_same(enemy)
	enemy.position = w.map.nearest_walkable(post + Vector2(0, 700))  # gone past 275 m: let it go
	for i in 200:
		w.step()
	assert_object(m.order_target).is_null()
	assert_int(m.order).is_equal(SimWorld.Order.GUARD)
	assert_float(m.position.distance_to(post)).is_less(20.0)


func test_stop_clears_order_and_target() -> void:
	var w := _mission().world
	var m := w.units[1]
	m.brain = null  # the world's own rules, no pbrain
	var enemy: SimUnit = _enemy_mech(w)
	w.order_attack(m, enemy)
	m.current_target = enemy
	w.order_stop(m)
	assert_int(m.order).is_equal(SimWorld.Order.HOLD)
	assert_object(m.current_target).is_null()


func _enemy_mech(w: SimWorld) -> SimUnit:
	return w.units.filter(func(u): return u is SimMech and u.team != 0)[0]
