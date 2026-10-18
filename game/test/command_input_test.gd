extends GdUnitTestSuite
## CommandInput against a live mission view: picking, ground hits, orders.

var view: Node3D


func before_test() -> void:
	view = load("res://scenes/mission_view.tscn").instantiate()
	add_child(view)
	await get_tree().process_frame
	await get_tree().process_frame


func after_test() -> void:
	view.queue_free()


func test_pick_player_mech_and_select() -> void:
	var input: CommandInput = view.input
	var m: SimMech = view.world.mechs[0]
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
	input._set_selection([w.mechs[0], w.mechs[1]])
	var focus: Vector3 = input.camera.focus
	input._command(input.camera.unproject_position(focus + Vector3(30, 0, 0)))
	assert_int(w.mechs[0].order).is_equal(SimWorld.Order.MOVE)
	assert_int(w.mechs[1].order).is_equal(SimWorld.Order.MOVE)
	var enemy: SimMech = w.mechs[4]
	enemy.position = w.mechs[0].position + Vector2(40, 0)  # bring it on screen
	view.views[enemy.id].sync(1.0)
	input._command(input.camera.unproject_position(view.views[enemy.id].aim_point()))
	assert_int(w.mechs[0].order).is_equal(SimWorld.Order.ATTACK)
	assert_object(w.mechs[0].order_target).is_same(enemy)
