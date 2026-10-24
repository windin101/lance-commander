extends GdUnitTestSuite
## SimMap: coordinates, heights, cell costs and pathing on mc2_01.

var map: SimMap


func before() -> void:
	map = SimMap.load_mission("mc2_01")
	map.build_pathing()


func test_dimensions_and_units() -> void:
	assert_int(map.vertices_per_side).is_equal(100)
	assert_int(map.cells_per_side).is_equal(300)
	assert_float(map.vertex_m).is_equal_approx(25.6, 0.0001)
	assert_float(map.half_m).is_equal_approx(1280.0, 0.001)
	assert_float(map.water_level_m).is_equal_approx(70.0, 0.001)


func test_cell_round_trip_and_orientation() -> void:
	assert_object(map.cell_of(Vector2(-1279.0, 1279.0))).is_equal(Vector2i(0, 0))  # north-west
	assert_object(map.cell_of(Vector2(1279.0, -1279.0))).is_equal(Vector2i(299, 299))
	for c in [Vector2i(0, 0), Vector2i(150, 42), Vector2i(299, 299)]:
		assert_object(map.cell_of(map.cell_center(c))).is_equal(c)


func test_height_matches_vertices() -> void:
	var p := Vector2(-map.half_m + 37 * map.vertex_m, map.half_m - 61 * map.vertex_m)
	assert_float(map.height_at(p)).is_equal_approx(map.vertex_height(61, 37), 0.001)
	var mid := p + Vector2(map.vertex_m / 2.0, 0)
	var expected := (map.vertex_height(61, 37) + map.vertex_height(61, 38)) / 2.0
	assert_float(map.height_at(mid)).is_equal_approx(expected, 0.001)


func test_deep_water_blocks_and_land_is_walkable() -> void:
	var deep := 0
	var walk := 0
	for row in range(0, 300, 7):
		for col in range(0, 300, 7):
			var c := Vector2i(col, row)
			if map.cell_flag(c, "deep") == 1:
				deep += 1
				assert_bool(map.is_walkable(c)).is_false()
			elif map.is_walkable(c):
				walk += 1
				assert_float(map.height_at(map.cell_center(c))).is_greater(map.water_level_m - 6.0)
	assert_int(deep).is_greater(0)
	assert_int(walk).is_greater(0)


func test_road_and_forest_costs() -> void:
	var saw_road := false
	var saw_forest := false
	for row in 300:
		for col in 300:
			var c := Vector2i(col, row)
			if not map.is_walkable(c):
				continue
			if map.cell_flag(c, "road") == 1 and map.cell_flag(c, "forest") == 0:
				assert_float(map.move_cost(c)).is_equal(25.0)
				saw_road = true
			elif map.cell_flag(c, "forest") == 1 and map.cell_flag(c, "road") == 0:
				assert_float(map.move_cost(c)).is_equal(150.0)
				saw_forest = true
		if saw_road and saw_forest:
			break
	assert_bool(saw_road).is_true()
	assert_bool(saw_forest).is_true()


func test_path_crosses_islands_on_walkable_cells_only() -> void:
	var a := map.nearest_walkable(Vector2(-640, 384))
	var b := map.nearest_walkable(Vector2(576, -448))
	var path := map.find_path(a, b)
	assert_int(path.size()).is_greater(10)
	assert_object(path[path.size() - 1]).is_equal(b)
	for p in path:
		assert_bool(map.is_walkable(map.cell_of(p))).is_true()


func test_no_path_into_deep_water() -> void:
	var a := map.nearest_walkable(Vector2(-640, 384))
	var sea := Vector2.ZERO
	for row in range(140, 160):
		var c := Vector2i(150, row)
		if map.cell_flag(c, "deep") == 1:
			sea = map.cell_center(c)
			break
	assert_int(map.find_path(a, sea).size()).is_equal(0)


## I10: reinforcements start on off-map cells (mc2_06 waves). As in the original (Move.cpp travelOffMap),
## a path that starts off the map may cross off-map cells, but nothing on the map may path into them.
func test_mover_starting_off_map_drives_in() -> void:
	var m := SimMap.load_mission("mc2_06")
	m.build_pathing()
	var start := Vector2i(-1, -1)
	for row in m.cells_per_side:
		for col in m.cells_per_side:
			var c := Vector2i(col, row)
			if m.cell_flag(c, "offmap") == 1 and m.move_cost(c, false, true) < SimMap.COST_BLOCKED:
				start = c
				break
		if start.x >= 0:
			break
	assert_bool(start.x >= 0).is_true()
	var from := m.cell_center(start)
	var goal := m.nearest_walkable(from, false, 60)
	assert_bool(m.cell_flag(m.cell_of(goal), "offmap") == 0).is_true()
	assert_int(m.find_path(from, goal).size()).is_greater(0)
	assert_int(m.find_path(goal, from).size()).is_equal(0)


## A unit the player steers (SimUnit.avoid_mines) paths round laid mines; everyone else walks
## straight through, as the original's pathfinder does (MCLib/Move.cpp:4391, avoidMines unread).
func test_avoid_mines_paths_round_a_minefield() -> void:
	var map := SimMap.load_mission("mc2_01")
	var start := map.nearest_walkable(Vector2(499.2, -380.0))
	var goal := map.nearest_walkable(start + Vector2(0, 120.0))
	var plain := map.find_path(start, goal)
	assert_bool(plain.size() > 3).is_true()
	var mid: Vector2i = map.cell_of(plain[plain.size() / 2])
	for dx in range(-6, 7):  # a line of mines across the plain path
		map.set_mine(mid + Vector2i(dx, 0), 1)
	var safe := map.find_path(start, goal, false, true)
	assert_bool(safe.size() > 0).is_true()
	for p in safe:
		assert_int(map.mine_at(map.cell_of(p))).is_not_equal(1)
	var through := map.find_path(start, goal)
	assert_bool(Array(through).any(func(p): return map.mine_at(map.cell_of(p)) == 1)).is_true()
