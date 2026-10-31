extends GdUnitTestSuite
## Walls block, gates pass their own team, destroyed walls and gates open the way, fences are walk-through and crushable (LANCE-21).

var rules: SimRules
var world: SimWorld


func before_test() -> void:
	rules = SimFixture.rules()
	world = SimWorld.new(rules, SimFixture.flat_map(), 1)


func _path_len(p: PackedVector2Array) -> float:
	var n := 0.0
	for i in range(1, p.size()):
		n += p[i - 1].distance_to(p[i])
	return n


## A light wall running north from (0, 0): post at -z end... local +z is (sin r, cos r), rotation 0 = north.
func _wall(pos: Vector2, rot := 0.0, app := "s_lightwall") -> SimStructure:
	var s := SimStructure.new()
	s.name = app
	s.model = app
	s.damage_level = 30.0
	s.team = -1
	s.position = pos
	s.facing = rot
	world.add_unit(s)
	s.wall_cells = SimWalls.wall_cells(world.map, app, pos, rot)
	world.map.block_cells(s.wall_cells)
	return s


func test_wall_footprint_blocks_the_straight_path_and_destroying_it_opens_it() -> void:
	var w := _wall(Vector2(0, 0))
	var a := Vector2(-60, 5)
	var b := Vector2(60, 5)
	var open_len := 120.0
	var p := world.map.find_path(a, b)
	assert_bool(p.is_empty()).is_false()
	assert_float(_path_len(p)).is_greater(open_len * 1.15)  # a detour round the wall
	for pt in p:
		assert_bool(w.wall_cells.has(world.map.cell_of(pt))).is_false()
	SimWalls.structure_down(world, w)
	assert_float(_path_len(world.map.find_path(a, b))).is_less(open_len * 1.05)


func test_gate_passes_its_own_team_and_shuts_enemies_until_destroyed() -> void:
	var gs := SimStructure.new()
	gs.name = "S_LightGate"; gs.model = "s_lightgate"; gs.damage_level = 25.0; gs.team = -1; gs.gate_team = 0
	gs.position = Vector2(0, 0)
	world.add_unit(gs)
	var parts := SimWalls.gate_parts(world.map, "s_lightgate", gs.position, 90.0)  # rotation 90: the line runs east-west, the door passes north-south
	gs.gate_id = 0
	world.map.block_cells(parts["sides"])
	world.map.add_gate(0, parts["door"], 0)
	gs.wall_cells = parts["sides"]
	world.gates.append(gs)
	assert_int((parts["door"] as Array).size()).is_greater(0)
	var a := Vector2(0, -60)
	var b := Vector2(0, 60)
	var own := world.map.find_path(a, b, false, false, 0)
	var enemy := world.map.find_path(a, b, false, false, 1)
	var own_len := _path_len(own)
	assert_float(own_len).is_less(132.0)  # straight through the door
	assert_float(_path_len(enemy)).is_greater(own_len + 8.0)  # round the 55 m line
	SimWalls.structure_down(world, gs)
	assert_float(_path_len(world.map.find_path(a, b, false, false, 1))).is_less(own_len + 4.0)  # open for everyone once destroyed (the sides stay)


func test_gate_locked_when_its_control_is_destroyed() -> void:
	var ctl := SimStructure.new()
	ctl.damage_level = 35.0; ctl.team = 0; ctl.position = Vector2(100, 100)
	world.add_unit(ctl)
	var gs := SimStructure.new()
	gs.model = "s_lightgate"; gs.damage_level = 25.0; gs.team = -1; gs.gate_team = 0; gs.position = Vector2(0, 0); gs.parent = ctl
	world.add_unit(gs)
	var parts := SimWalls.gate_parts(world.map, "s_lightgate", gs.position, 90.0)
	gs.gate_id = 0
	world.map.block_cells(parts["sides"])
	world.map.add_gate(0, parts["door"], 0)
	world.gates.append(gs)
	SimWalls.update_gates(world)
	assert_bool(world.map.gate_passable(0, 0)).is_true()
	ctl.damage = ctl.damage_level
	ctl.status = SimUnit.Status.DESTROYED
	SimWalls.update_gates(world)
	assert_bool(world.map.gate_passable(0, 0)).is_false()


func test_gate_opens_for_an_own_team_mover_in_range_only() -> void:
	var gs := SimStructure.new()
	gs.model = "s_lightgate"; gs.damage_level = 25.0; gs.team = -1; gs.gate_team = 0; gs.position = Vector2(0, 0); gs.object_index = 7
	world.add_unit(gs)
	var parts := SimWalls.gate_parts(world.map, "s_lightgate", gs.position, 90.0)
	gs.gate_id = 0
	world.map.add_gate(0, parts["door"], 0)
	world.gates.append(gs)
	var own := SimFixture.mech("atlas", rules); own.team = 0; own.position = Vector2(20, 0)
	var foe := SimFixture.mech("atlas", rules); foe.team = 1; foe.position = Vector2(-10, 0)
	world.add_unit(own)
	world.add_unit(foe)
	world.events.clear()
	SimWalls.update_gates(world)
	assert_bool(gs.gate_open).is_true()
	own.position = Vector2(400, 0)
	SimWalls.update_gates(world)
	assert_bool(gs.gate_open).is_false()  # the enemy next to it doesn't open it


# --- fences ---------------------------------------------------------------------------------

func test_fence_is_walk_through_for_pathing_and_crushed_by_a_moving_mech() -> void:
	var before := world.map.find_path(Vector2(-60, 0), Vector2(60, 0))
	world.add_prop(3, "wirefence", Vector2(0, -4), 0.0)  # runs along -y from (0, -4)... a segment crossing the path's line
	var after := world.map.find_path(Vector2(-60, 0), Vector2(60, 0))
	assert_int(after.size()).is_equal(before.size())  # no cell changed
	assert_int(world.units.size()).is_equal(0)  # a prop is no unit: no AI target, no objective
	var idle := SimFixture.mech("atlas", rules)
	idle.position = Vector2(0, -6)
	world.add_unit(idle)
	for i in 20:
		world.step()
	assert_bool(world.events.any(func(e): return e["type"] == "prop_destroyed")).is_false()  # standing on it doesn't crush it
	idle.exists = false
	var m := SimFixture.mech("atlas", rules)
	m.position = Vector2(-20, -6)
	world.add_unit(m)
	world.order_move(m, Vector2(20, -6))
	for i in 400:
		world.step()
		if world.events.any(func(e): return e["type"] == "prop_destroyed"):
			break
	assert_bool(world.events.any(func(e): return e["type"] == "prop_destroyed")).is_true()  # a mech walking over it crushes it


func test_explosion_hurts_a_fence_by_its_damage_and_a_far_one_not_at_all() -> void:
	world.add_prop(1, "wirefence", Vector2(0, 0), 0.0)  # level 8
	world.add_prop(2, "wirefence", Vector2(200, 0), 0.0)
	world.explosion(Vector2(0.5, -3), 4.0, 6.0)  # half the level
	var hit: Array = world.events.filter(func(e): return e["type"] == "prop_hit")
	assert_int(hit.size()).is_equal(1)
	assert_float(float(hit[0]["frac"])).is_equal_approx(0.5, 0.01)
	assert_int(int(hit[0]["index"])).is_equal(1)
	world.explosion(Vector2(0.5, -3), 10.0, 6.0)
	assert_bool(world.events.any(func(e): return e["type"] == "prop_destroyed" and int(e["index"]) == 1)).is_true()


func test_prop_direction_matches_the_view_node() -> void:
	for deg in [0.0, 45.0, 90.0, -135.0, 180.0]:
		var node := Node3D.new()
		node.rotation.y = PI - deg_to_rad(deg)  # ObjectsView
		var local_back := node.basis * Vector3(0, 0, -1)
		var d := SimProps.direction(deg)
		assert_float(local_back.x).is_equal_approx(d.x, 0.001)
		assert_float(-local_back.z).is_equal_approx(d.y, 0.001)  # sim y is world -z
		node.free()
