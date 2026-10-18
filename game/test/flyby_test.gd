extends GdUnitTestSuite
## Intro flyby: movie mode, camera path, hand-off to the comms sequence, skip.

var view: Node3D


func before_test() -> void:
	view = load("res://scenes/mission_view.tscn").instantiate()
	add_child(view)
	await get_tree().process_frame


func after_test() -> void:
	view.queue_free()


func test_flyby_runs_then_hands_off() -> void:
	var fb: IntroFlyby = view.flyby
	assert_bool(fb.is_running()).is_true()
	assert_bool(view.hud.visible).is_false()
	assert_object(view.sequencer.view).is_null()
	var start_focus: Vector3 = view.camera.focus
	for i in 200:
		fb._process(0.1)
	assert_bool(fb.is_running()).is_false()
	assert_bool(view.hud.visible).is_true()
	assert_object(view.sequencer.view).is_not_null()
	var end := Vector2(2453.333, -1984.0) * 0.2
	assert_float(Vector2(view.camera.focus.x, -view.camera.focus.z).distance_to(end)).is_less(1.0)
	assert_float(Vector2(start_focus.x, -start_focus.z).distance_to(Vector2(3648.0, 448.0) * 0.2)).is_less(1.0)


func test_escape_skips_to_end() -> void:
	var fb: IntroFlyby = view.flyby
	var ev := InputEventKey.new()
	ev.keycode = KEY_ESCAPE
	ev.pressed = true
	fb._unhandled_input(ev)
	assert_bool(fb.is_running()).is_false()
	assert_bool(view.hud.visible).is_true()
