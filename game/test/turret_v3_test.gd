extends GdUnitTestSuite
## v3 turret family (LANCE-39, tools/art/v3/bld_turrets.py): three states, two LODs on library materials, bounds against the
## originals on every axis, a yawing "Turret" node (with a "Gun" child) on every gun, the pop-up hook, and charred wrecks.

const GUNS := ["mediumautocannonturret", "lrmturret", "srmturret", "pulselaserturret", "gaussturret", "longtomturret", "orbitalturret", "guntower"]
const POPUPS := ["lrmpopup", "srmpopup", "autocannonpopup", "autocannoncamo2", "autocannoncamo4", "srmcamo2"]
const BUILDINGS := ["s_turretcontrol", "l_turretcontrol", "d_turretcontrol", "bturretcontrol", "l_turretgenerator", "spotlight"]


func _aabb(root: Node3D, lod := "") -> AABB:
	var box := AABB()
	var first := true
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		if lod != "" and not mi.name.begins_with(lod):
			continue
		var m := mi as MeshInstance3D
		var xf := Transform3D.IDENTITY
		var n: Node = m
		while n and n != root:
			xf = (n as Node3D).transform * xf
			n = n.get_parent()
		var b: AABB = xf * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


func test_family_has_three_states_two_lods_on_library_materials_and_original_bounds() -> void:
	for app in GUNS + POPUPS + BUILDINGS:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var seen := 0
				for mi in node.find_children(lod + "*", "MeshInstance3D", true, false):
					var mesh: Mesh = (mi as MeshInstance3D).mesh
					for i in mesh.get_surface_count():
						var nm := mesh.surface_get_material(i).resource_name
						assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
							.override_failure_message("%s%s %s surface %d: '%s'" % [app, st, lod, i, nm]).is_true()
					seen += 1
				assert_int(seen).override_failure_message("%s%s has no %s" % [app, st, lod]).is_greater(0)
				if st != "":
					continue
				var b := _aabb(node, lod)
				var tol := 3.0
				for ax in ["x", "z"]:
					assert_float(b.position[ax]).override_failure_message("%s %s %s0 %.1f vs %.1f" % [app, lod, ax, b.position[ax], ob.position[ax]]).is_between(ob.position[ax] - tol, ob.position[ax] + tol)
					assert_float(b.end[ax]).override_failure_message("%s %s %s1 %.1f vs %.1f" % [app, lod, ax, b.end[ax], ob.end[ax]]).is_between(ob.end[ax] - tol, ob.end[ax] + tol)
				assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 4.5, ob.end.y + 2.5)
				if app in POPUPS:
					assert_float(b.position.y).override_failure_message("%s %s bottom %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(ob.position.y - 3.0, ob.position.y + 3.0)
				else:
					assert_float(b.position.y).override_failure_message("%s %s base y %.1f" % [app, lod, b.position.y]).is_between(-0.6, 0.6)
			node.queue_free()


func test_every_gun_has_a_yawing_turret_node_and_the_pedestal_stays_put() -> void:
	for app in GUNS + POPUPS:
		for st in ["", "_damaged"]:
			var node: Node3D = (load(BuildingV3.model_path(app, st)) as PackedScene).instantiate()
			add_child(node)
			var t := node.find_child("Turret", true, false) as Node3D
			assert_object(t).override_failure_message("%s%s has no Turret node" % [app, st]).is_not_null()
			var base := node.find_child("Base", true, false) as Node3D
			var before := _aabb(base)
			t.rotation.y = deg_to_rad(90.0)  # what set_turret_yaw does
			assert_vector(_aabb(base).size).is_equal_approx(before.size, Vector3(0.01, 0.01, 0.01))
			if app != "spotlight" and app != "guntower":
				assert_object(t.find_child("Gun", true, false)).override_failure_message("%s has no Gun" % app).is_not_null()
			node.queue_free()


func test_both_lods_get_their_distance_ranges_on_every_part() -> void:
	for app in ["lrmturret", "lrmpopup", "orbitalturret", "spotlight"]:
		var node: Node3D = (load(BuildingV3.model_path(app)) as PackedScene).instantiate()
		BuildingV3.set_lods(node)
		var n0 := 0
		var n1 := 0
		for mi in node.find_children("lod*", "MeshInstance3D", true, false):
			if mi.name.begins_with("lod0"):
				assert_float((mi as GeometryInstance3D).visibility_range_end).is_equal(BuildingV3.LOD_M)
				n0 += 1
			else:
				assert_float((mi as GeometryInstance3D).visibility_range_begin).is_equal(BuildingV3.LOD_M)
				n1 += 1
		assert_int(n0).is_greater(1)
		assert_int(n1).is_equal(n0)
		node.free()


func test_wrecks_are_charred_to_the_dark_sets() -> void:
	var ok := ["roofdark", "slate", "rust", "interior", "decal"]
	for app in GUNS + POPUPS + BUILDINGS:
		var node: Node3D = (load(BuildingV3.model_path(app, "_destroyed")) as PackedScene).instantiate()
		for mi in node.find_children("lod0*", "MeshInstance3D", true, false):
			var mesh: Mesh = (mi as MeshInstance3D).mesh
			for i in mesh.get_surface_count():
				var nm := mesh.surface_get_material(i).resource_name.trim_prefix("bv3_")
				assert_bool(nm in ok).override_failure_message("%s wreck uses '%s'" % [app, nm]).is_true()
		node.free()


# --- the pop-up hook (ObjectsView.set_turret_pop): doors open first, then the lift raises the turret ---
func test_popup_models_have_a_lift_and_two_door_leaves() -> void:
	for app in POPUPS:
		var node: Node3D = (load(BuildingV3.model_path(app)) as PackedScene).instantiate()
		for nm in ["Pop", "pop_door_l", "pop_door_r", "Turret", "Gun"]:
			assert_object(node.find_child(nm, true, false)).override_failure_message("%s has no %s" % [app, nm]).is_not_null()
		assert_object(node.find_child("Pop", true, false).find_child("Turret", true, false)).is_not_null()  # the turret rides the lift
		node.free()


func test_pop_hook_states() -> void:
	var view := ObjectsView.new()
	add_child(view)
	var node: Node3D = (load(BuildingV3.model_path("lrmpopup")) as PackedScene).instantiate()
	view.add_child(node)
	view.nodes[3] = node
	var pop := node.find_child("Pop", true, false) as Node3D
	var dl := node.find_child("pop_door_l", true, false) as Node3D
	var dr := node.find_child("pop_door_r", true, false) as Node3D
	var y0 := pop.position.y
	view._apply_pop(0.0, 3)  # closed
	assert_float(dl.rotation.z).is_equal_approx(0.0, 0.001)
	assert_float(pop.position.y).is_equal_approx(y0, 0.001)
	view._apply_pop(ObjectsView.POP_DOOR_FRAC * 0.5, 3)  # doors half open, the lift has not moved
	assert_float(dl.rotation.z).is_equal_approx(deg_to_rad(ObjectsView.POP_DOOR_DEG) * 0.5, 0.001)
	assert_float(dr.rotation.z).is_equal_approx(-deg_to_rad(ObjectsView.POP_DOOR_DEG) * 0.5, 0.001)  # mirrored
	assert_float(pop.position.y).is_equal_approx(y0, 0.001)
	view._apply_pop(ObjectsView.POP_DOOR_FRAC, 3)  # doors fully open, lift just starting
	assert_float(dl.rotation.z).is_equal_approx(deg_to_rad(ObjectsView.POP_DOOR_DEG), 0.001)
	assert_float(pop.position.y).is_equal_approx(y0, 0.001)
	view._apply_pop(0.65, 3)  # mid rise: between rest and the top
	assert_float(pop.position.y).is_between(y0 + 0.5, y0 + ObjectsView.POP_RISE_M - 0.5)
	view._apply_pop(1.0, 3)  # open
	assert_float(pop.position.y).is_equal_approx(y0 + ObjectsView.POP_RISE_M, 0.001)
	assert_float(view.pop_progress(3)).is_equal_approx(1.0, 0.001)
	# the sim calls set_turret_pop every frame: only a change starts a tween; a model with no Pop node is ignored
	view.set_turret_pop(3, false)
	assert_bool(view._pop[3][3]).is_false()
	view.set_turret_pop(3, false)  # unchanged: nothing restarts
	view.set_turret_pop(3, true)
	assert_bool(view._pop[3][3]).is_true()
	var plain: Node3D = (load(BuildingV3.model_path("lrmturret")) as PackedScene).instantiate()
	view.add_child(plain)
	view.nodes[4] = plain
	view.set_turret_pop(4, true)  # no Pop node: ignored, no error
	assert_float(view.pop_progress(4)).is_equal(0.0)
	view._appearance[3] = "lrmpopup"
	view.destroy(3)
	assert_bool(view._pop.has(3)).is_false()
	view.queue_free()
