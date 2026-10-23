extends GdUnitTestSuite
## CommandInput against a live mission view: picking, ground hits, orders.

var view: Node3D


func before_test() -> void:
	view = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	await get_tree().process_frame


func after_test() -> void:
	view.queue_free()


func test_pick_player_mech_and_select() -> void:
	var input: CommandInput = view.input
	var m: SimMech = view.world.units[0]
	var screen := input.camera.unproject_position(view.views[m.id].aim_point())
	assert_object(input.mech_at(screen, 0)).is_same(m)
	input._select_click(screen, false)
	assert_int(input.selection.size()).is_equal(1)
	assert_bool(view.views[m.id].selected).is_true()


func test_ground_hit_matches_terrain() -> void:
	var input: CommandInput = view.input
	var focus: Vector3 = input.camera.focus
	var screen := input.camera.unproject_position(focus)
	var g = input.ground_at(screen)
	assert_object(g).is_not_null()
	assert_float((g as Vector2).distance_to(Vector2(focus.x, -focus.z))).is_less(6.0)


func test_right_click_moves_and_attacks() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0], w.units[1]])
	var focus: Vector3 = input.camera.focus
	input._command(input.camera.unproject_position(focus + Vector3(30, 0, 0)))
	assert_int(w.units[0].order).is_equal(SimWorld.Order.MOVE)
	assert_int(w.units[1].order).is_equal(SimWorld.Order.MOVE)
	var enemy: SimUnit = w.units.filter(func(u): return u is SimMech and u.team != 0)[0]
	enemy.position = w.units[0].position + Vector2(40, 0)  # bring it on screen
	view.views[enemy.id].sync(1.0)
	input._command(input.camera.unproject_position(view.views[enemy.id].aim_point()))
	assert_int(w.units[0].order).is_equal(SimWorld.Order.ATTACK)
	assert_object(w.units[0].order_target).is_same(enemy)


func test_right_click_building_orders_attack() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var hangar: SimUnit = view.sm.structure_near(Vector2(3221.333, -277.333))
	input.camera.focus = Vector3(hangar.position.x, 0, -hangar.position.y)
	input.camera._apply()
	input._set_selection([w.units[0]])
	var p := TerrainView.to_3d(hangar.position, w.map.height_at(hangar.position) + 4.0)
	input._command(input.camera.unproject_position(p))
	assert_int(w.units[0].order).is_equal(SimWorld.Order.ATTACK)
	assert_object(w.units[0].order_target).is_same(hangar)


func test_box_drag_threshold_is_10px() -> void:
	assert_float(CommandInput.DRAG_PX).is_equal(10.0)


func test_group_assign_select_and_add() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var a: SimUnit = w.units[0]
	var b: SimUnit = w.units[1]
	input._set_selection([a])
	input.assign_group(1)
	input._set_selection([b])
	input.assign_group(2)
	input.select_group(1, false)
	assert_array(input.selection).contains_exactly([a])
	input.select_group(2, true)  # Shift+2 adds
	assert_array(input.selection).contains_exactly([a, b])
	input.select_group(2, true)  # all of it selected already: Shift+2 drops it
	assert_array(input.selection).contains_exactly([a])
	assert_array(input.groups_of(a)).contains_exactly([1])


func test_group_keys() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0], w.units[1]])
	var k := InputEventKey.new()
	k.pressed = true
	k.keycode = KEY_3
	k.ctrl_pressed = true
	input._key(k)  # Ctrl+3 assigns
	input._set_selection([])
	k.ctrl_pressed = false
	input._key(k)  # 3 selects
	assert_int(input.selection.size()).is_equal(2)


func test_e_selects_units_on_screen() -> void:
	var input: CommandInput = view.input
	input._set_selection([])
	input.select_visible(false)
	assert_int(input.selection.size()).is_greater(0)
	assert_bool(input.selection.all(func(u): return u.team == input.player_team)).is_true()


func test_double_click_selects_group_and_follows() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var a: SimUnit = w.units[0]
	input._set_selection([a, w.units[1]])
	input.assign_group(4)
	input._set_selection([])
	input._double_click(input.camera.unproject_position(view.views[a.id].aim_point()))
	assert_int(input.selection.size()).is_equal(2)
	assert_object(view.camera.following).is_same(a)
	view.camera.pan_to(Vector2(a.position.x + 50, a.position.y))  # minimap click stops following
	assert_object(view.camera.following).is_null()


func test_camera_uses_original_projection() -> void:
	assert_int(view.camera.keep_aspect).is_equal(Camera3D.KEEP_WIDTH)
	assert_float(view.camera.fov).is_equal(40.0)


func test_compass_follows_focus() -> void:
	var cam: RtsCamera = view.camera
	var c: CameraCompass = view.compass
	# mc2_01's script opens with a movie (setMovieMode); a dev view skips it as Esc does, and the
	# script then fades and calls endMovieMode itself. The compass stays hidden until then.
	var seen: bool = view.world.movie_mode
	for i in 400:
		if seen and not view.world.movie_mode:
			break
		if view.world.movie_mode:
			seen = true
			view.world.force_movie_end = true
		view.sm.step()
	assert_bool(seen).is_true()
	assert_bool(view.world.movie_mode).is_false()
	cam.pan_to(Vector2(cam.focus.x + 60, -cam.focus.z + 40))
	for i in 8:
		await get_tree().process_frame
	assert_float(Vector2(c.global_position.x, c.global_position.z).distance_to(Vector2(cam.focus.x, cam.focus.z))).is_less(0.01)
	assert_float(c.global_position.y).is_equal_approx(cam.focus.y + 0.3, 0.01)
	assert_vector(c.rotation).is_equal(Vector3.ZERO)
	assert_bool(c.visible).is_true()
	var k := InputEventKey.new()
	k.pressed = true
	k.keycode = KEY_BACKSLASH
	c._unhandled_input(k)
	await get_tree().process_frame
	assert_bool(c.visible).is_false()
	view.world.movie_mode = true
	c.enabled = true
	await get_tree().process_frame
	assert_bool(c.visible).is_false()  # hidden in movie mode


# --- I82: the command palette's modes ----------------------------------------------------

func _ground_screen(input: CommandInput, offset: Vector3) -> Vector2:
	return input.camera.unproject_position(input.camera.focus + offset)


func test_right_click_walks_unless_run_is_armed() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0]])
	input._command(_ground_screen(input, Vector3(30, 0, 0)))
	assert_bool(w.units[0].move_run).is_false()
	assert_bool(input.toggle_mode("run")).is_true()
	assert_str(input.order_mode).is_equal("run")
	input._command(_ground_screen(input, Vector3(-30, 0, 0)))
	assert_bool(w.units[0].move_run).is_true()
	assert_str(input.order_mode).is_equal("")  # a move uses the mode (setDefaultSpeed)


func test_held_mode_key_arms_only_while_down() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0]])
	input.hold_mode_key(KEY_SPACE, true)
	assert_bool(input.mode_on("run")).is_true()
	input._command(_ground_screen(input, Vector3(30, 0, 0)))
	assert_bool(w.units[0].move_run).is_true()
	assert_bool(input.mode_on("run")).is_true()  # still held
	input.hold_mode_key(KEY_SPACE, false)
	assert_bool(input.mode_on("run")).is_false()


func test_jump_mode_needs_jump_jets_and_jumps_the_click() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var ww: SimUnit = w.units[0]  # Werewolf: jump jets
	var bw: SimUnit = w.units[1]  # Bushwacker: none
	input._set_selection([ww, bw])
	assert_bool(input.toggle_mode("jump")).is_false()
	assert_bool(input.mode_on("jump")).is_false()
	input._set_selection([ww])
	assert_bool(input.toggle_mode("jump")).is_true()
	var screen := input.camera.unproject_position(TerrainView.to_3d(ww.position + Vector2(40, 0), w.map.height_at(ww.position + Vector2(40, 0))))
	input._command(screen)
	assert_int(ww.order).is_equal(SimWorld.Order.JUMP)
	assert_str(input.order_mode).is_equal("")


func test_guard_mode_guards_the_point() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[1]])
	input.toggle_mode("guard")
	input.toggle_mode("run")  # run combines with guard
	assert_bool(input.mode_on("guard") and input.mode_on("run")).is_true()
	input._command(_ground_screen(input, Vector3(30, 0, 0)))
	assert_int(w.units[1].order).is_equal(SimWorld.Order.GUARD)
	assert_str(input.order_mode).is_equal("")
	input._set_selection([w.units[0]])  # a jumper
	input.toggle_mode("guard")
	input.toggle_mode("jump")  # jump is alone
	assert_bool(input.mode_on("guard")).is_false()


func test_fire_from_position_attack_keeps_run() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var m: SimUnit = w.units[1]
	input._set_selection([m])
	var enemy: SimUnit = w.units.filter(func(u): return u is SimMech and u.team != 0)[0]
	enemy.position = m.position + Vector2(40, 0)
	view.views[enemy.id].sync(1.0)
	input.toggle_mode("run")
	input.toggle_mode("fire_from_position")
	input._command(input.camera.unproject_position(view.views[enemy.id].aim_point()))
	assert_int(m.order).is_equal(SimWorld.Order.ATTACK)
	assert_bool(m.attack_pursue).is_false()
	assert_bool(input.mode_on("fire_from_position")).is_false()  # used by the attack
	assert_bool(input.mode_on("run")).is_true()  # an attack leaves Run on (missiongui.cpp:1893)


func test_hold_toggles_and_stop_resets() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0], w.units[1]])
	w.units[0].hold_position = true
	input.toggle_hold_position()  # not all hold -> all hold
	assert_bool(w.units[0].hold_position and w.units[1].hold_position).is_true()
	assert_bool(input.mode_on("hold")).is_true()
	input.toggle_hold_position()
	assert_bool(w.units[0].hold_position or w.units[1].hold_position).is_false()
	input._command(_ground_screen(input, Vector3(30, 0, 0)))
	input.toggle_mode("guard")
	input.fire_from_position = true
	input.stop()
	assert_int(w.units[0].order).is_equal(SimWorld.Order.HOLD)
	assert_str(input.order_mode).is_equal("")


func _press(input: CommandInput, key: int, down := true) -> void:
	var e := InputEventKey.new()
	e.keycode = key
	e.pressed = down
	if down:
		input._key(e)
	else:
		input._input(e)


func test_palette_hotkeys() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0]])
	_press(input, KEY_H)
	assert_bool(w.units[0].hold_position).is_true()
	for k in [[KEY_J, "jump"], [KEY_G, "guard"], [KEY_SPACE, "run"], [KEY_C, "fire_from_position"]]:
		_press(input, k[0])
		assert_bool(input.mode_on(k[1])).is_true()
		_press(input, k[0], false)
		assert_bool(input.mode_on(k[1])).is_false()
	input.toggle_mode("guard")
	_press(input, KEY_BACKSPACE)
	assert_str(input.order_mode).is_equal("")


func test_force_fire_on_an_ally_and_on_the_ground() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var a: SimUnit = w.units[0]
	var ally: SimUnit = w.units[1]
	ally.position = a.position + Vector2(40, 0)
	view.views[ally.id].sync(1.0)
	input._set_selection([a])
	assert_bool(input.toggle_mode("force_fire")).is_true()
	input._command(input.camera.unproject_position(view.views[ally.id].aim_point()))
	assert_int(a.order).is_equal(SimWorld.Order.ATTACK)
	assert_object(a.order_target).is_same(ally)  # forceShot: a friend too (missiongui.cpp:3208)
	assert_bool(input.mode_on("force_fire")).is_false()  # one shot
	input.toggle_mode("force_fire")
	var focus: Vector3 = input.camera.focus
	input._command(input.camera.unproject_position(focus + Vector3(-30, 0, 0)))
	assert_int(a.order).is_equal(SimWorld.Order.ATTACK_POINT)


func test_range_buttons_set_the_attack_range() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	input._set_selection([w.units[0]])
	assert_str(input.attack_range_mode()).is_equal("")
	input.toggle_mode("long")
	assert_bool(input.mode_on("long")).is_true()
	input.toggle_mode("short")  # a radio group
	assert_bool(input.mode_on("long")).is_false()
	assert_str(input.attack_range_mode()).is_equal("short")
	var enemy: SimUnit = w.units.filter(func(u): return u is SimMech and u.team != 0)[0]
	enemy.position = w.units[0].position + Vector2(40, 0)
	view.views[enemy.id].sync(1.0)
	input._command(input.camera.unproject_position(view.views[enemy.id].aim_point()))
	assert_str(w.units[0].range_mode).is_equal("short")
	assert_float(w.ordered_fire_range(w.units[0])).is_equal(30.0)  # (60 - 0) / 2 (mover.cpp:5907)


func test_waypoints_queue_and_run_in_order() -> void:
	var input: CommandInput = view.input
	var w: SimWorld = view.world
	var m: SimUnit = w.units[0]
	input._set_selection([m])
	var a := w.map.nearest_walkable(m.position + Vector2(40, 0))
	var b := w.map.nearest_walkable(m.position + Vector2(40, 40))
	m.order_queue.append(func(): input._order_now(m, "move", a, {}))
	m.order_queue.append(func(): input._order_now(m, "move", b, {}))
	input._queued.append(m)
	input.run_waypoints()
	var reached_a := false
	for i in 400:
		view.sm.step()
		view.world.events.clear()
		reached_a = reached_a or m.position.distance_to(a) < 6.0
		if m.order_queue.is_empty() and m.order == SimWorld.Order.HOLD:
			break
	assert_bool(reached_a).is_true()
	assert_float(m.position.distance_to(b)).is_less(8.0)
	assert_bool(m.queue_running).is_false()


func test_lay_mines_needs_a_minelayer() -> void:
	var input: CommandInput = view.input
	input._set_selection([view.world.units[0]])
	assert_bool(input.toggle_mode("lay_mines")).is_false()
