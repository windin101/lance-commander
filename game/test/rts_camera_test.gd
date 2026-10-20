extends GdUnitTestSuite
## RtsCamera on its own: the original's limits, speeds and snaps (no mission loaded).

var cam: RtsCamera


func before_test() -> void:
	cam = auto_free(RtsCamera.new())
	add_child(cam)


func test_edge_scroll_zone() -> void:
	var scr := Vector2(1600, 900)
	assert_vector(RtsCamera.edge_dir(Vector2(800, 450), scr)).is_equal(Vector2.ZERO)
	assert_vector(RtsCamera.edge_dir(Vector2(4, 450), scr)).is_equal(Vector2(-1, 0))
	assert_vector(RtsCamera.edge_dir(Vector2(5, 450), scr)).is_equal(Vector2.ZERO)  # 5 px zone: 0-4
	assert_vector(RtsCamera.edge_dir(Vector2(1595, 450), scr)).is_equal(Vector2(1, 0))
	assert_vector(RtsCamera.edge_dir(Vector2(800, 0), scr)).is_equal(Vector2(0, 1))  # top = forward
	assert_vector(RtsCamera.edge_dir(Vector2(800, 899), scr)).is_equal(Vector2(0, -1))
	assert_vector(RtsCamera.edge_dir(Vector2(0, 0), scr)).is_equal(Vector2(-1, 1))  # corner: both axes
	assert_vector(RtsCamera.edge_dir(Vector2(-10, 450), scr)).is_equal(Vector2.ZERO)  # outside the window


func test_defaults_match_original() -> void:
	assert_float(cam.pitch_deg).is_equal(35.0)
	assert_float(cam.distance).is_equal(240.0)


func test_zoom_limits_depend_on_pitch() -> void:
	assert_float(RtsCamera.max_distance_for(10.0)).is_equal_approx(299.4, 0.01)
	assert_float(RtsCamera.max_distance_for(88.0)).is_equal_approx(319.4, 0.01)
	cam.pitch_deg = 35.0
	cam.distance = 5000.0
	cam._apply()
	assert_float(cam.distance).is_equal_approx(RtsCamera.max_distance_for(35.0), 0.01)
	assert_float(cam.distance).is_equal_approx(305.8, 0.1)
	cam.distance = 1.0
	cam._apply()
	assert_float(cam.distance).is_equal(112.0)
	cam.pitch_deg = 120.0
	cam._apply()
	assert_float(cam.pitch_deg).is_equal(88.0)
	cam.pitch_deg = 0.0
	cam._apply()
	assert_float(cam.pitch_deg).is_equal(10.0)


func test_rotation_snaps() -> void:
	cam.yaw_deg = 0.0
	cam.tick(0.001, Vector2.ZERO, 1, 0, 0)  # a tap is one whole snap
	assert_float(cam.yaw_deg).is_equal(-11.25)
	cam.tick(0.001, Vector2.ZERO, 0, 0, 0)
	cam.tick(0.001, Vector2.ZERO, -1, 0, 0)
	assert_float(cam.yaw_deg).is_equal(0.0)
	cam.tick(0.001, Vector2.ZERO, 0, 0, 0)
	for i in 10:  # held for 1 s: the first snap plus 337.5 deg/s in 11.25 deg steps
		cam.tick(0.1, Vector2.ZERO, -1, 0, 0)
	assert_float(fmod(cam.yaw_deg, 11.25)).is_equal_approx(0.0, 0.001)
	assert_float(cam.yaw_deg).is_equal_approx(11.25 + 303.75, 0.001)


func test_pan_speed_scales_with_zoom_and_clears_follow() -> void:
	cam.yaw_deg = 0.0
	cam.distance = 240.0
	var s := cam.scale_factor()
	cam.following = SimUnit.new()
	cam.tick(1.0, Vector2(0, 1), 0, 0, 0)  # 1 s forward = north = -Z
	assert_float(-cam.focus.z).is_equal_approx(66.5 / s, 0.01)
	assert_object(cam.following).is_null()


func test_focus_clamped_inside_map_edge() -> void:
	cam.bounds_half = 1000.0
	cam.pan_to(Vector2(5000, -5000))
	assert_float(cam.focus.x).is_equal(796.0)
	assert_float(cam.focus.z).is_equal(796.0)


func test_terrain_clearance_raises_pitch() -> void:
	cam.height_at = func(p: Vector2) -> float: return 0.0 if p.length() < 5.0 else 150.0  # high ground behind
	cam.pitch_deg = 35.0
	cam._apply()
	assert_float(cam.pitch_deg).is_equal(35.0)  # the setting is kept
	assert_float(cam.view_pitch).is_between(52.0, 53.0)  # asin(190 / 240), in 0.25 deg steps
	assert_float(cam.global_position.y).is_greater_equal(190.0)


func test_focus_eases_over_big_height_jumps() -> void:
	var h := [0.0]
	cam.height_at = func(_p: Vector2) -> float: return h[0]
	cam._apply()
	h[0] = 20.0
	cam._apply(0.016)
	assert_float(cam.focus.y).is_equal(20.0)  # small step: snaps
	h[0] = 120.0
	cam._apply(0.1)
	assert_float(cam.focus.y).is_equal_approx(20.0 + 100.0 * 0.5 * 0.1, 0.001)


func test_home_resets_view() -> void:
	cam.home_yaw = 45.0
	cam.yaw_deg = 100.0
	cam.pitch_deg = 70.0
	cam.distance = 150.0
	cam.reset_view()
	assert_float(cam.yaw_deg).is_equal(45.0)
	assert_float(cam.pitch_deg).is_equal(35.0)
	assert_float(cam.distance).is_equal(240.0)
