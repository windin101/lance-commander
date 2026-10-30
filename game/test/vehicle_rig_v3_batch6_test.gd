extends GdUnitTestSuite
## The v3 vehicles of LANCE-19 batch 6 (tools/art/v3/veh_*.py): VehicleRig finds each one's moving parts, the wheels are full
## discs of a sane radius, the tread strips are valid, the ambulance steers its front axle.

const DIR := "res://assets/v3/vehicles/"
# unit: [turret node (or ""), extra turrets, gun node (or ""), tracks, wheels, steer pivots, min radius, max radius]
const UNITS := {
	"monsoon": ["Monsoon_Turret", 0, "", 0, 0, 0, 0.0, 1.0],
	"trooptransport": ["", 0, "", 2, 12, 0, 0.25, 0.6],
	"ambulance": ["", 0, "", 0, 6, 2, 0.5, 0.8],
}


func _load(unit: String) -> Array:
	var side := {}
	var sp := DIR + unit + ".v3.json"
	if FileAccess.file_exists(sp):
		side = JSON.parse_string(FileAccess.get_file_as_string(sp))
	var model: Node3D = (load(DIR + unit + ".glb") as PackedScene).instantiate()
	add_child(model)
	return [model, side, VehicleRig.build(model, side)]


func test_rig_parts_found_for_every_unit() -> void:
	for unit in UNITS:
		if not ResourceLoader.exists(DIR + unit + ".glb"):
			continue
		var u: Array = UNITS[unit]
		var l := _load(unit)
		var rig: VehicleRig = l[2]
		assert_object(rig).is_not_null()
		if u[0] != "":
			assert_object(rig.turret).is_not_null()
			assert_str(String(rig.turret.name)).is_equal(u[0])
			assert_bool(rig.turret is MeshInstance3D).is_true()
		else:
			assert_object(rig.turret).is_null()
		assert_int(rig.turrets.size()).is_equal(u[1])
		for t in rig.turrets:
			assert_bool(t is MeshInstance3D).is_true()
		if u[2] != "":
			assert_object(rig.gun).is_not_null()
			assert_str(String(rig.gun.name)).is_equal(u[2])
			assert_bool(rig.gun is MeshInstance3D).is_true()
			assert_int((l[1]["gun_pitch"] as Array).size()).is_equal(2)
		else:
			assert_object(rig.gun).is_null()
		assert_int(rig.tracks.size()).is_equal(u[3])
		assert_int(rig.wheels.size()).is_equal(u[4])
		assert_int(rig.steers.size()).is_equal(u[5])
		for w in rig.wheels:
			assert_bool(w is MeshInstance3D).is_true()
			assert_float(float(rig._radius[w])).is_between(u[6], u[7])
		(l[0] as Node3D).queue_free()


func test_tread_strips_are_valid() -> void:
	for unit in UNITS:
		if not ResourceLoader.exists(DIR + unit + ".glb") or UNITS[unit][3] == 0:
			continue
		var tracks: Dictionary = (_load(unit)[1] as Dictionary).get("tracks", {})
		var belts: Array = ["track_l", "track_r"]
		for k in belts:
			assert_bool(tracks.has(k)).is_true()
			var s: Array = tracks[k]
			assert_int(s.size()).is_equal(3)
			assert_float(float(s[0])).is_between(0.0, 1.0)
			assert_float(float(s[1])).is_greater(0.0)
			assert_float(float(s[0]) + float(s[1])).is_less_equal(1.0)
			assert_float(float(s[2])).is_greater(0.0)


func test_wheels_spin_and_belts_scroll() -> void:
	for unit in UNITS:
		if not ResourceLoader.exists(DIR + unit + ".glb") or UNITS[unit][4] == 0:
			continue
		var l := _load(unit)
		var rig: VehicleRig = l[2]
		var w: Node3D = rig.wheels[0]
		rig.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
		var q0 := w.basis.get_rotation_quaternion()
		rig.update(Vector2(0, 0.5), 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
		assert_float(q0.angle_to(w.basis.get_rotation_quaternion())).is_equal_approx(0.5 / float(rig._radius[w]), 1e-3)
		if rig.tracks.size() >= 2:
			assert_float(rig.belt.x).is_equal_approx(0.5, 1e-5)
			assert_float(rig._half_track).is_greater(0.9)
		(l[0] as Node3D).queue_free()


func test_turret_and_gun_move() -> void:
	for unit in UNITS:
		if not ResourceLoader.exists(DIR + unit + ".glb"):
			continue
		var u: Array = UNITS[unit]
		var l := _load(unit)
		var rig: VehicleRig = l[2]
		var t: Node3D = rig.turret if rig.turret else (rig.turrets[0] if not rig.turrets.is_empty() else null)
		if t == null:
			continue
		var rest := t.basis
		rig.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
		rig.update(Vector2.ZERO, 0.0, 90.0, 60.0, Vector2.ZERO, 0.0)
		assert_bool(t.basis.is_equal_approx(rest)).is_false()
		for tt in rig.turrets:  # a twin mount: every half turns
			assert_bool(tt.basis.is_equal_approx(rest)).is_false()
		if u[2] != "":
			var gb := rig.gun.basis
			var gp: Array = l[1]["gun_pitch"]
			rig.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2(30.0, 40.0), 1.0)  # a target well above the gun: it rises
			assert_float(rig.gun_pitch).is_between(float(gp[0]), float(gp[1]))
			assert_float(rig.gun_pitch).is_greater(1.0)
			assert_bool(rig.gun.basis.is_equal_approx(gb)).is_false()
		(l[0] as Node3D).queue_free()


func test_wheeled_units_steer_their_front_wheels() -> void:
	for unit in ["ambulance"]:
		if not ResourceLoader.exists(DIR + unit + ".glb"):
			continue
		var l := _load(unit)
		var rig: VehicleRig = l[2]
		assert_int(rig.steers.size()).is_equal(2)
		for s in rig.steers:
			assert_bool(String(s.name).begins_with("steer_")).is_true()
			var kids := s.get_children().filter(func(c): return String(c.name).begins_with("wheel_"))
			assert_int(kids.size()).is_equal(1)
			assert_bool((rig.wheels as Array).has(kids[0])).is_true()
		assert_float(rig._wheelbase).is_greater(1.5)
		var rest := (rig.steers[0] as Node3D).basis
		rig.update(Vector2.ZERO, 0.0, 0.0, 60.0, Vector2.ZERO, 0.0)
		rig.update(Vector2(0, 5), 20.0, 0.0, 60.0, Vector2.ZERO, 1.0)
		assert_float(rig.steer).is_greater(3.0)
		assert_bool((rig.steers[0] as Node3D).basis.is_equal_approx(rest)).is_false()
		(l[0] as Node3D).queue_free()
