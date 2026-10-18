extends GdUnitTestSuite
## Ground vehicle rules (gvehicl.cpp) on mc2_01's vehicle types.

const S := SimVehicle.Section

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_01", 2)


func _first(type_name: String) -> SimVehicle:
	for u in sm.world.units:
		if u is SimVehicle and u.name.to_lower().begins_with(type_name):
			return u
	return null


func test_loaded_stats() -> void:
	var h := _first("harasser")
	assert_bool(h.hover).is_true()
	assert_float(h.run_speed).is_equal(23.0)
	assert_float(h.walk_speed).is_equal(9.0)
	assert_float(h.armor[S.TURRET]).is_equal(4.0)
	assert_int(h.num_weapons).is_equal(2)
	assert_bool(h.uses_heat).is_false()
	assert_float(h.turn_rate).is_equal(240.0)  # 20 t
	var c := _first("centipede")
	assert_float(sm.world.fire_arc(c)).is_equal(12.5)  # no turret: hull must point at the target


func test_hit_location_turret_on_high_average_roll() -> void:
	var h := _first("harasser")
	h.position = Vector2.ZERO
	h.facing = 0.0
	var rng := SimRng.new()
	rng.force([90, 60])  # (90+60)/2 = 75 >= 70
	assert_int(h.roll_hit_location(sm.world.rules, rng, Vector2(0, 100))).is_equal(S.TURRET)
	rng.force([10, 20, 10, 20, 10, 20])
	assert_int(h.roll_hit_location(sm.world.rules, rng, Vector2(0, 100))).is_equal(S.FRONT)
	assert_int(h.roll_hit_location(sm.world.rules, rng, Vector2(-100, 0))).is_equal(S.LEFT)
	assert_int(h.roll_hit_location(sm.world.rules, rng, Vector2(0, -100))).is_equal(S.REAR)


func test_armor_then_internal_then_destroyed() -> void:
	var h := _first("harasser")
	var r := sm.world.rules
	h.take_hit(r, sm.world.rng, 4.0, S.FRONT, 143, 0.0)
	assert_float(h.armor[S.FRONT]).is_equal(2.0)
	assert_bool(h.is_destroyed()).is_false()
	h.take_hit(r, sm.world.rng, 2.5, S.FRONT, 143, 0.0)  # 2 armour, 0.5 into 1 internal
	assert_float(h.internal[S.FRONT]).is_equal(0.5)
	h.take_hit(r, sm.world.rng, 0.5, S.FRONT, 143, 0.0)
	assert_bool(h.is_destroyed()).is_true()


func test_lrm_carrier_death_splash() -> void:
	var w := sm.world
	var lrmc := _first("lrmcarrier")
	var victim := _first("infantry")
	victim.position = lrmc.position + Vector2(5, 0)
	var armour_before := 0.0
	for a in victim.armor:
		armour_before += a
	lrmc.status = SimUnit.Status.DESTROYED
	w.step()
	var armour_after := 0.0
	for a in victim.armor:
		armour_after += a
	assert_bool(armour_after < armour_before or victim.is_destroyed()).is_true()


func test_hover_crosses_deep_water_ground_does_not() -> void:
	var map := sm.world.map
	var a := map.nearest_walkable(Vector2(-640, 384))
	var sea := Vector2.ZERO
	for row in range(140, 160):
		var c := Vector2i(150, row)
		if map.cell_flag(c, "deep") == 1:
			sea = map.cell_center(c)
			break
	assert_int(map.find_path(a, sea).size()).is_equal(0)
	assert_int(map.find_path(a, sea, true).size()).is_greater(0)
