extends GdUnitTestSuite
## SimWorld on mc2_01: spawning, movement orders, attacks, determinism.

func _mission(seed_value: int = 1) -> SimMission:
	return SimMission.load_mission(GameData, "mc2_01", seed_value)


func _team(w: SimWorld, team: int) -> Array[SimMech]:
	var out: Array[SimMech] = []
	for m in w.mechs:
		if m.team == team:
			out.append(m)
	return out


func test_spawns_mechs_and_lists_skipped_parts() -> void:
	var sm := _mission()
	assert_int(sm.world.mechs.size()).is_equal(6)
	assert_int(_team(sm.world, 0).size()).is_equal(3)
	assert_int(sm.skipped.size()).is_equal(23)  # 4 Centipede, 4 Harasser, 7 LRMC, 8 infantry
	var ww := sm.world.mechs[0]
	assert_str(ww.name).is_equal("Werewolf")
	assert_bool(ww.is_player).is_true()
	assert_float(ww.position.x).is_equal_approx(499.2, 0.01)
	assert_float(ww.walk_speed).is_greater(0.0)
	for m in sm.world.mechs:
		assert_bool(sm.world.map.is_walkable(sm.world.map.cell_of(m.position))).is_true()


func test_move_order_arrives() -> void:
	var w := _mission().world
	var m := w.mechs[0]
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
	var m := w.mechs[1]  # Bushwacker, run 23 m/s
	w.order_move(m, w.map.nearest_walkable(m.position + Vector2(-300, 0)))
	for i in 30:
		w.step()
	assert_float(m.speed).is_greater(15.0)
	assert_int(m.body_state).is_equal(SimMech.BodyState.RUNNING)


func test_attack_order_closes_and_damages() -> void:
	var w := _mission(7).world
	var attacker := w.mechs[1]
	var target: SimMech = null
	for m in w.mechs:
		if m.name == "Urbanmech":
			target = m
			break
	assert_object(target).is_not_null()
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
		w.order_attack(w.mechs[1], w.mechs[5])
		w.order_attack(w.mechs[2], w.mechs[5])
		for i in 600:
			w.step()
	for i in a.mechs.size():
		assert_object(a.mechs[i].position).is_equal(b.mechs[i].position)
		assert_object(a.mechs[i].armor).is_equal(b.mechs[i].armor)


func test_turns_to_engage_target_behind() -> void:
	var w := _mission(5).world
	var a := w.mechs[1]
	var t: SimMech = null
	for m in w.mechs:
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
