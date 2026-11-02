extends GdUnitTestSuite
## Start facing of mission units. The original faces a mover at rotation r along (0,-1) turned by
## Rotate(-r), i.e. (sin r, -cos r) (gameobj.h:571-578, mover.h:1106-1114, mathfunc.cpp:34-45). The sim
## moves along (sin h, cos h) for a heading h (sim_world.gd), so a part placed at rotation r starts at
## heading 180 - r. The campaign force and reinforcements are added at rotation 0 (logistics.cpp:733,
## missiongui.cpp:4159), which faces south.


func _dir(h: float) -> Vector2:
	return Vector2(sin(deg_to_rad(h)), cos(deg_to_rad(h)))


func test_heading_reproduces_the_originals_rotation_vector() -> void:
	for r in [0.0, 45.0, 90.0, 135.0, 180.0, -90.0, 270.0, 315.0, -135.0]:
		var want := Vector2(sin(deg_to_rad(r)), -cos(deg_to_rad(r)))
		var h := SimMission.heading_from_rotation(r)
		assert_float(h).is_greater_equal(0.0)
		assert_float(h).is_less(360.0)
		assert_float(_dir(h).distance_to(want)).is_less(1e-4)
	assert_float(SimMission.heading_from_rotation(0.0)).is_equal_approx(180.0, 1e-4)  # rotation 0 faces south
	assert_float(SimMission.heading_from_rotation(180.0)).is_equal_approx(0.0, 1e-4)  # rotation 180 faces north
	assert_float(SimMission.heading_from_rotation(90.0)).is_equal_approx(90.0, 1e-4)  # east/west are unchanged


func test_mission_parts_start_at_180_minus_rotation() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01", 1, false)
	var checked := 0
	for u in sm.world.units:
		if not u.is_mover() or u.part_index < 1:
			continue
		var r := float(sm.fit["Part%d" % u.part_index].get("Rotation", 0.0))
		assert_float(_dir(u.facing).distance_to(Vector2(sin(deg_to_rad(r)), -cos(deg_to_rad(r))))).is_less(1e-4)
		checked += 1
	assert_int(checked).is_greater(20)


func test_campaign_force_and_reinforcements_start_facing_south() -> void:
	var force := [{"chassis": "atlas", "variant": 0, "pilot": "pmwflash", "gunnery": 60.0, "piloting": 55.0},
		{"chassis": "hunchback", "variant": 0, "pilot": "pmwhacksaw", "gunnery": 50.0, "piloting": 50.0}]
	var sm := SimMission.load_mission(GameData, "mc2_02", 1, false, force)
	var lance := sm.world.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover())
	assert_int(lance.size()).is_equal(2)
	for m in lance:
		assert_float(m.facing).is_equal_approx(180.0, 1e-4)
		assert_float(m.prev_facing).is_equal_approx(180.0, 1e-4)
	var at: Vector2 = lance[0].position
	assert_float(sm.support._spawn_mech("atlas", at, "").facing).is_equal_approx(180.0, 1e-4)
	assert_float(sm.support._spawn_vehicle("apc1", at).facing).is_equal_approx(180.0, 1e-4)
