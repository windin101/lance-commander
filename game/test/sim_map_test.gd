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
