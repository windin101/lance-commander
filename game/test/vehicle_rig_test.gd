extends GdUnitTestSuite
## VehicleRig (LANCE-17): turret traverse, gun elevation, wheel spin, steering and track scroll from the sim pose.


func _part(parent: Node3D, part_name: String, at: Vector3, size := Vector3(0.4, 0.8, 0.8)) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = part_name
	var box := BoxMesh.new()
	box.size = size
	mi.mesh = box
	mi.position = at
	parent.add_child(mi)
	return mi


## A test vehicle as the v3 pipeline lays it out: +Z forward, steering pivots at the front, tracks either side.
func _model() -> Node3D:
	var root := Node3D.new()
	var hull := _part(root, "hull", Vector3(0, 1, 0), Vector3(3, 1, 6))
	var tur := _part(hull, "turret", Vector3(0, 1, 0), Vector3(2, 0.6, 2))
	_part(tur, "gun", Vector3(0, 0.2, 1.5), Vector3(0.2, 0.2, 2))
	for side in [-1.0, 1.0]:
		var s := Node3D.new()
		s.name = "steer_f%s" % ("l" if side < 0 else "r")
		s.position = Vector3(side * 1.4, 0.4, 2.0)
		root.add_child(s)
		_part(s, "wheel_f%s" % ("l" if side < 0 else "r"), Vector3.ZERO)
		_part(root, "wheel_r%s" % ("l" if side < 0 else "r"), Vector3(side * 1.4, 0.4, -2.0))
	_part(root, "track_l", Vector3(1.2, 0.4, 0), Vector3(0.5, 0.8, 5))
	_part(root, "track_r", Vector3(-1.2, 0.4, 0), Vector3(0.5, 0.8, 5))
	return root


func _rig(root: Node3D) -> VehicleRig:
	return VehicleRig.build(root, {"gun_pitch": [-5, 20], "tracks": {"track_l": [0.5, 0.25, 12.0], "track_r": [0.75, 0.25, 12.0]}})


func test_travel_is_signed_along_the_facing() -> void:
	assert_float(VehicleRig.travel(Vector2.ZERO, Vector2(0, 2), 0.0)).is_equal_approx(2.0, 1e-5)  # north, facing north
	assert_float(VehicleRig.travel(Vector2.ZERO, Vector2(0, -2), 0.0)).is_equal_approx(-2.0, 1e-5)  # backing up
	assert_float(VehicleRig.travel(Vector2.ZERO, Vector2(3, 0), 90.0)).is_equal_approx(3.0, 1e-5)  # east, facing east
	assert_float(VehicleRig.travel(Vector2.ZERO, Vector2(3, 0), 0.0)).is_equal_approx(0.0, 1e-5)  # sideways: no roll


func test_belts_counter_rotate_on_the_spot() -> void:
	var b := VehicleRig.belts(0.0, 90.0, 1.0)  # a quarter turn clockwise on the spot
	assert_float(b.x).is_equal_approx(PI / 2.0, 1e-5)  # left belt forward
	assert_float(b.y).is_equal_approx(-PI / 2.0, 1e-5)  # right belt back
	var s := VehicleRig.belts(2.0, 0.0, 1.0)
	assert_float(s.x).is_equal_approx(2.0, 1e-5)
	assert_float(s.y).is_equal_approx(2.0, 1e-5)


func test_steering_follows_the_curve() -> void:
	# a 10 m radius right turn with a 3 m wheelbase: atan(3/10)
	var a := VehicleRig.steer_for(1.0, rad_to_deg(0.1), 3.0, 0.0)
	assert_float(a).is_equal_approx(rad_to_deg(atan(0.3)), 1e-3)
	assert_float(VehicleRig.steer_for(1.0, -rad_to_deg(0.1), 3.0, 0.0)).is_equal_approx(-a, 1e-3)
	assert_float(VehicleRig.steer_for(0.0, 45.0, 3.0, 7.0)).is_equal(7.0)  # turning on the spot: hold the wheel
	assert_float(VehicleRig.steer_for(0.1, 90.0, 3.0, 0.0)).is_equal(VehicleRig.MAX_STEER)


func test_turret_takes_the_short_way_at_its_rate() -> void:
	assert_float(VehicleRig.turret_step(170.0, -170.0, 10.0, 0.5)).is_equal_approx(175.0, 1e-4)
	assert_float(VehicleRig.turret_step(0.0, 3.0, 60.0, 0.1)).is_equal_approx(3.0, 1e-4)
	assert_float(VehicleRig.turret_step(0.0, 90.0, 60.0, 0.1)).is_equal_approx(6.0, 1e-4)


func test_rig_poses_the_parts() -> void:
	var root := _model()
	add_child(root)
	var r := _rig(root)
	assert_object(r).is_not_null()
	assert_str(String(r.turret.name)).is_equal("turret")
	assert_str(String(r.gun.name)).is_equal("gun")
	assert_int(r.wheels.size()).is_equal(4)
	assert_int(r.steers.size()).is_equal(2)
	assert_int(r.tracks.size()).is_equal(2)
	r.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	# turret 90 degrees clockwise (to the right): its forward (+Z) swings to -X in model space (right of +Z forward,
	# seen from above with the view's rotation.y = PI - facing)
	r.update(Vector2.ZERO, 0.0, 90.0, 60.0, Vector2.ZERO, 0.0)
	var fwd: Vector3 = r.turret.basis * Vector3.FORWARD * -1.0
	assert_vector(fwd).is_equal_approx(Vector3(-1, 0, 0), Vector3.ONE * 1e-4)
	# drive 1 m forward: a 0.4 m wheel rolls 2.5 rad, its top moving forward (+Z)
	var w := r.wheels[2] if String(r.wheels[0].name).begins_with("wheel_f") else r.wheels[0]
	r.update(Vector2(0, 1), 0.0, 90.0, 60.0, Vector2.ZERO, 0.0)
	var top := w.basis * Vector3.UP
	assert_float(atan2(top.z, top.y)).is_equal_approx(2.5, 1e-3)
	# gun elevates toward a target 10 m up at 40 m, within its +20 limit
	for i in 60:
		r.update(Vector2(0, 1), 0.0, 90.0, 60.0, Vector2(10.0, 40.0), 0.1)
	assert_float(r.gun_pitch).is_greater(5.0)
	assert_float(r.gun_pitch).is_less_equal(20.0)
	root.queue_free()


func test_tracks_scroll_and_reverse_with_the_turn() -> void:
	var root := _model()
	add_child(root)
	var r := _rig(root)
	r.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	r.update(Vector2.ZERO, 30.0, 0.0, 60.0, Vector2.ZERO, 0.1)  # on the spot, clockwise
	assert_float(r.belt.x).is_greater(0.0)
	assert_float(r.belt.y).is_less(0.0)
	var t: MeshInstance3D = r.tracks[0]
	var strip: Vector3 = t.get_instance_shader_parameter("track_strip")
	assert_float(strip.y).is_equal_approx(0.25, 1e-5)
	assert_float(strip.z).is_between(0.0, 1.0)
	root.queue_free()


func test_one_piece_hd_vehicles_get_no_rig() -> void:
	# the HD hunter's turret node is an empty marker over one merged hd_body: turning it would move only the muzzles
	if ResourceLoader.exists("res://assets/vehicles/hunter_hd.glb"):
		var hd: Node3D = load("res://assets/vehicles/hunter_hd.glb").instantiate()
		assert_object(VehicleRig.build(hd, {})).is_null()
		hd.free()
	if ResourceLoader.exists("res://assets/vehicles/hunter.glb"):
		var v1: Node3D = load("res://assets/vehicles/hunter.glb").instantiate()
		var r := VehicleRig.build(v1, {})
		assert_object(r).is_not_null()
		assert_str(String(r.turret.name)).is_equal("Hunter_Turret")
		v1.free()


func test_split_treads_scroll_per_side() -> void:
	# the MOG: two tread units a side, track_l0/l1 and track_r0/r1, each with its own strip
	var root := Node3D.new()
	_part(root, "hull", Vector3(0, 1, 0), Vector3(3, 1, 6))
	for i in 2:
		_part(root, "track_l%d" % i, Vector3(1.5, 0.4, -1.5 + 3.0 * i), Vector3(0.5, 0.8, 2.5))
		_part(root, "track_r%d" % i, Vector3(-1.5, 0.4, -1.5 + 3.0 * i), Vector3(0.5, 0.8, 2.5))
	add_child(root)
	var strips := {}
	for k in ["track_l0", "track_l1", "track_r0", "track_r1"]:
		strips[k] = [0.5, 0.25, 6.0]
	var r := VehicleRig.build(root, {"tracks": strips})
	assert_int(r.tracks.size()).is_equal(4)
	assert_float(r._half_track).is_equal_approx(1.5, 1e-4)
	r.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	r.update(Vector2.ZERO, 30.0, 0.0, 60.0, Vector2.ZERO, 0.1)  # on the spot, clockwise: left forward, right back
	for t: MeshInstance3D in r.tracks:
		var z: float = (t.get_instance_shader_parameter("track_strip") as Vector3).z
		var left := String(t.name).begins_with("track_l")
		assert_float(z).is_equal_approx(fposmod((r.belt.x if left else r.belt.y) / 6.0, 1.0), 1e-5)
	assert_float(r.belt.x).is_greater(0.0)
	assert_float(r.belt.y).is_less(0.0)
	root.queue_free()


func test_sidecar_spin_parts_turn_at_their_rate() -> void:
	# the Mobile HQ's radar: named in the sidecar's "spin", turning clockwise at a constant rate, moving or not
	var root := Node3D.new()
	var hull := _part(root, "hull", Vector3(0, 1, 0), Vector3(3, 1, 6))
	var dish := _part(hull, "hq_radar", Vector3(0, 1.5, 0), Vector3(1, 0.2, 1))
	add_child(root)
	var r := VehicleRig.build(root, {"spin": {"hq_radar": 40.0, "no_such_node": 10.0}})
	assert_object(r).is_not_null()
	assert_int(r.spins.size()).is_equal(1)
	r.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	r.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 2.25)  # 90 degrees clockwise: +Z swings to -X
	assert_vector(dish.basis * Vector3.BACK).is_equal_approx(Vector3(-1, 0, 0), Vector3.ONE * 1e-4)
	root.queue_free()


func test_every_v3_wheel_turns_about_its_own_centre() -> void:
	# A wheel whose mesh sits off its node origin orbits the pivot and reads as an egg (Lee, 2026-10-30: the
	# Centipede's and Partisan's were lowered/raised by moving the mesh, not the node, 165-182 mm off centre)
	var dir := "res://assets/v3/vehicles/"
	for f in DirAccess.get_files_at(dir):
		if not f.ends_with(".glb"):
			continue
		var m: Node3D = (load(dir + f) as PackedScene).instantiate()
		for w in m.find_children("wheel_*", "Node3D", true, false):
			var box := AABB()
			var first := true
			for mi in ([w] if w is MeshInstance3D else []) + w.find_children("*", "MeshInstance3D", true, false):
				var bb: AABB = (mi as MeshInstance3D).get_aabb() if mi == w else (mi as MeshInstance3D).transform * (mi as MeshInstance3D).get_aabb()
				box = bb if first else box.merge(bb)
				first = false
			if first:
				continue
			var c := box.get_center()
			assert_float(Vector2(c.y, c.z).length()).override_failure_message(
				"%s %s: mesh centre %s is off the pivot" % [f, w.name, c]).is_less(0.01)
		m.free()
