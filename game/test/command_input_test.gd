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
