extends GdUnitTestSuite
## The v3 Hunter (LANCE-18, tools/art/v3/hunter_*.py) as the first vehicle with separate rigid moving parts: VehicleRig.build finds
## the turret and both track belts, and the sidecar's tread strip is valid.

const GLB := "res://assets/v3/vehicles/hunter.glb"
const SIDECAR := "res://assets/v3/vehicles/hunter.v3.json"


func _sidecar() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(SIDECAR))


func test_rig_finds_turret_and_both_tracks() -> void:
	if not ResourceLoader.exists(GLB):
		return
	var model: Node3D = (load(GLB) as PackedScene).instantiate()
	add_child(model)
	var rig := VehicleRig.build(model, _sidecar())
	assert_object(rig).is_not_null()
	assert_object(rig.turret).is_not_null()
	assert_str(String(rig.turret.name)).is_equal("Hunter_Turret")
	assert_bool(rig.turret is MeshInstance3D).is_true()  # a turret with a mesh: the HD models' empty marker nodes don't turn
	assert_int(rig.tracks.size()).is_equal(2)
	var names := rig.tracks.map(func(t): return String(t.name))
	assert_array(names).contains_exactly_in_any_order(["track_l", "track_r"])
	for t in rig.tracks:
		assert_object((t as MeshInstance3D).mesh).is_not_null()
	# track_l is at +X (+Z is forward), so the rig reads the real track gauge from the two belt nodes
	assert_float(rig._half_track).is_greater(0.9)
	# Lee's rule (2026-10-25): the road wheels are seen to turn. Eight a side, each with a mesh and a real radius
	assert_int(rig.wheels.size()).is_equal(16)
	for w in rig.wheels:
		assert_float(float(rig._radius[w])).is_between(0.15, 0.4)
	var w0: Node3D = rig.wheels[0]
	rig.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	var q0 := w0.basis.get_rotation_quaternion()
	rig.update(Vector2(0, 0.5), 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	assert_float(q0.angle_to(w0.basis.get_rotation_quaternion())).is_equal_approx(0.5 / float(rig._radius[w0]), 1e-3)
	# road wheels, idler and sprocket: 8 a side, full discs of our own geometry pivoted on their axles
	assert_int(rig.wheels.size()).is_equal(16)
	for w in rig.wheels:
		assert_bool(String(w.name).begins_with("wheel_")).is_true()
		assert_bool(w is MeshInstance3D).is_true()
		var rad: float = rig._radius[w]
		assert_float(rad).is_between(0.2, 0.3)  # half the mesh height: 0.266 m road wheels, 0.215 m idler and sprocket
	model.queue_free()


func test_sidecar_tread_strip_is_valid() -> void:
	if not ResourceLoader.exists(SIDECAR):
		return
	var tracks: Dictionary = _sidecar().get("tracks", {})
	for k in ["track_l", "track_r"]:
		assert_bool(tracks.has(k)).is_true()
		var s: Array = tracks[k]
		assert_int(s.size()).is_equal(3)
		assert_float(float(s[0])).is_between(0.0, 1.0)
		assert_float(float(s[1])).is_greater(0.0)
		assert_float(float(s[0]) + float(s[1])).is_less_equal(1.0)  # the strip lies inside the atlas
		assert_float(float(s[2])).is_greater(0.0)  # belt_m: metres per strip period


func test_turret_turns_and_belts_scroll() -> void:
	if not ResourceLoader.exists(GLB):
		return
	var model: Node3D = (load(GLB) as PackedScene).instantiate()
	add_child(model)
	var rig := VehicleRig.build(model, _sidecar())
	var rest := rig.turret.basis
	rig.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
	rig.update(Vector2(0, 0.2), 0.0, 90.0, 60.0, Vector2.ZERO, 0.0)
	assert_bool(rig.turret.basis.is_equal_approx(rest)).is_false()
	assert_float(rig.belt.x).is_equal_approx(0.2, 1e-5)
	var w: Node3D = rig.wheels[0]
	var before := w.basis
	rig.update(Vector2(0, 0.6), 0.0, 90.0, 60.0, Vector2.ZERO, 0.0)
	assert_bool(w.basis.is_equal_approx(before)).is_false()  # the wheels spin with the distance travelled
	model.queue_free()


func test_a_destroyed_v3_vehicle_keeps_its_model_burnt() -> void:
	# Lee, 2026-10-31: no 2001 wreck swapped in under the v3 art; the v3 model stays, scorched and still
	if not ResourceLoader.exists(GLB):
		return
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit
	for x in sm.world.units:
		if not (x is SimMech):
			u = x
			break
	u.model = "hunter"
	var v := MechView.new()
	add_child(v)
	v.setup(u, sm.world.map)
	var before := v.model
	assert_object(v.rig).is_not_null()
	u.status = SimUnit.Status.DESTROYED
	v.sync(1.0)
	if MechView.v3_wreck_path("hunter_v3", "vehicles", "hunter") != "":
		# a destroyed variant exists (tools/art/v3/wreck_mesh.py): it is swapped in, burn baked into its vertices
		assert_bool(v.model != before).is_true()
		assert_object(v.rig).is_null()
		v.queue_free()
		return
	assert_object(v.model).is_same(before)
	assert_object(v.rig).is_null()
	var mi := v.model.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D
	assert_float(float((mi.material_override as ShaderMaterial).get_shader_parameter("scorch"))).is_equal(1.0)
	v.queue_free()
