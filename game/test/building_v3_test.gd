extends GdUnitTestSuite
## v3 buildings (LANCE-21): a model under assets/v3/objects takes the shared library materials, ObjectsView prefers it
## behind ArtV3, swaps to the damaged state at half damage and to the destroyed state on destroy, and falls back to the
## current art for a building with no v3 model.


func after_test() -> void:
	ArtV3.enabled = ArtV3._detect()


func test_every_surface_gets_a_library_material() -> void:
	var path := BuildingV3.model_path("largefueltank")
	assert_str(path).is_not_empty()
	var node: Node3D = (load(path) as PackedScene).instantiate()
	BuildingV3.dress(node)
	var seen := 0
	for mi in node.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			assert_object(mesh.surface_get_material(i)).is_instanceof(ShaderMaterial)
			seen += 1
	assert_int(seen).is_greater(6)
	node.free()


func test_states_exist_and_switch_off_with_art_v3() -> void:
	for st in ["", "_damaged", "_destroyed"]:
		assert_str(BuildingV3.model_path("largefueltank", st)).is_not_empty()
	assert_str(BuildingV3.model_path("pine1")).is_empty()  # no v3 model: the current art stays
	ArtV3.enabled = false
	assert_str(BuildingV3.model_path("largefueltank")).is_empty()


func test_damage_swaps_then_destroy_swaps() -> void:
	ArtV3.enabled = true
	var view := ObjectsView.new()
	add_child(view)
	var intact: Node3D = view._instance_state(BuildingV3.model_path("largefueltank"))
	view.add_child(intact)
	view.nodes[7] = intact
	view._appearance[7] = "largefueltank"
	view.set_damage(7, 0.3)
	assert_object(view.nodes[7]).is_same(intact)
	view.set_damage(7, 0.6)
	assert_object(view.nodes[7]).is_not_same(intact)
	var hurt: Node3D = view.nodes[7]
	view.destroy(7)
	assert_object(view.nodes[7]).is_not_same(hurt)
	view.queue_free()


const STORAGE_FAMILY := ["largefueltank", "smallfueltank", "pipetank", "liquidstorage", "watertower", "grainstorage",
	"civstoragea", "civstorageb", "civstoragec"]


func test_storage_family_has_three_states_with_two_lods() -> void:
	for app in STORAGE_FAMILY:
		for st in ["", "_damaged", "_destroyed"]:
			var path := BuildingV3.model_path(app, st)
			assert_str(path).is_not_empty()
			var node: Node3D = (load(path) as PackedScene).instantiate()
			assert_object(node.find_child("lod0", true, false)).is_not_null()
			assert_object(node.find_child("lod1", true, false)).is_not_null()
			BuildingV3.dress(node)
			assert_float((node.find_child("lod0", true, false) as GeometryInstance3D).visibility_range_end).is_equal(BuildingV3.LOD_M)
			assert_float((node.find_child("lod1", true, false) as GeometryInstance3D).visibility_range_begin).is_equal(BuildingV3.LOD_M)
			node.free()


const HANGAR_FAMILY := ["quonsetclean", "quonset", "quonset2", "hangar", "vehiclehangar", "repairbay", "portable"]


func test_hangar_family_has_three_states_with_two_lods() -> void:
	for app in HANGAR_FAMILY:
		for st in ["", "_damaged", "_destroyed"]:
			var path := BuildingV3.model_path(app, st)
			assert_str(path).is_not_empty()
			var node: Node3D = (load(path) as PackedScene).instantiate()
			assert_object(node.find_child("lod0", true, false)).is_not_null()
			assert_object(node.find_child("lod1", true, false)).is_not_null()
			node.free()


const WALL_FAMILY := ["wirefence", "razorwirefence", "woodenfence", "shantyfence", "sandbagwall", "sandbagbunker", "tripodbarricade", "corrigatedmetalbarricade",
	"s_lightwall", "s_mediumwall", "s_heavywall", "l_lightwall", "d_heavywall", "s_lightpost"]


func test_wall_and_fence_family_has_three_states_with_two_lods() -> void:
	for app in WALL_FAMILY:
		for st in ["", "_damaged", "_destroyed"]:
			var path := BuildingV3.model_path(app, st)
			assert_str(path).is_not_empty()
			var node: Node3D = (load(path) as PackedScene).instantiate()
			assert_object(node.find_child("lod0", true, false)).is_not_null()
			assert_object(node.find_child("lod1", true, false)).is_not_null()
			node.free()


func test_v3_gates_have_sliding_door_leaves_until_destroyed() -> void:
	for app in ["s_lightgate", "l_mediumgate", "d_heavygate"]:
		var node: Node3D = (load(BuildingV3.model_path(app)) as PackedScene).instantiate()
		assert_object(node.find_child("door_l", true, false)).is_not_null()
		assert_object(node.find_child("door_r", true, false)).is_not_null()
		node.free()
		var wreck: Node3D = (load(BuildingV3.model_path(app, "_destroyed")) as PackedScene).instantiate()
		assert_object(wreck.find_child("door_l", true, false)).is_null()
		wreck.free()


# --- every wall, post and gate model covers the original's run, at both detail levels, with resolvable materials ---

func _mesh_aabb(n: Node) -> AABB:
	var out := AABB()
	var first := true
	var list: Array = n.find_children("*", "MeshInstance3D", true, false)
	if n is MeshInstance3D:
		list.append(n)
	for mi in list:
		var m := mi as MeshInstance3D
		if m.mesh == null:
			continue
		var bb: AABB = m.mesh.get_aabb() if m == n else (n.global_transform.affine_inverse() * m.global_transform) * m.mesh.get_aabb()
		out = bb if first else out.merge(bb)
		first = false
	return out


func test_wall_post_gate_lods_cover_the_originals_run_and_use_library_materials() -> void:
	var seen := 0
	for style in ["s_", "l_", "d_"]:
		for kind in ["lightwall", "mediumwall", "heavywall", "lightpost", "mediumpost", "heavypost", "lightgate", "mediumgate", "heavygate"]:
			var app: String = style + kind
			var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
			add_child(orig)
			var ob := _mesh_aabb(orig)
			orig.queue_free()
			for st in ["", "_damaged", "_destroyed"]:
				var node: Node3D = (load(BuildingV3.model_path(app, st)) as PackedScene).instantiate()
				BuildingV3.set_lods(node)
				add_child(node)
				for lod in ["lod0", "lod1"]:
					var l := node.find_child(lod, true, false) as MeshInstance3D
					assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
					var mesh := l.mesh
					for i in mesh.get_surface_count():
						var nm := mesh.surface_get_material(i).resource_name if mesh.surface_get_material(i) else ""
						assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
							.override_failure_message("%s%s %s surface %d: material '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
					if st == "":
						var tol := 3.5 if kind.ends_with("post") else 2.5  # l_ posts carry a chamfered cap deeper than the original's
						var b := l.mesh.get_aabb()
						# the run axis is z (body away from the post at -z): both ends within tol of the original's
						assert_float(b.position.z).override_failure_message("%s %s run starts at %.1f, original %.1f" % [app, lod, b.position.z, ob.position.z]) \
							.is_between(ob.position.z - tol, ob.position.z + tol)
						assert_float(b.end.z).override_failure_message("%s %s run ends at %.1f, original %.1f" % [app, lod, b.end.z, ob.end.z]) \
							.is_between(ob.end.z - tol, ob.end.z + tol)
						# every axis: the piece's origin must sit where the original's does (a post offset or sunk underground fails here)
						assert_float(b.position.x).override_failure_message("%s %s x starts at %.1f, original %.1f" % [app, lod, b.position.x, ob.position.x]).is_between(ob.position.x - 2.5, ob.position.x + 2.5)
						assert_float(b.end.x).override_failure_message("%s %s x ends at %.1f, original %.1f" % [app, lod, b.end.x, ob.end.x]).is_between(ob.end.x - 2.5, ob.end.x + 2.5)
						assert_float(b.position.y).override_failure_message("%s %s sits at y %.1f (underground or floating)" % [app, lod, b.position.y]).is_between(-0.6, 0.6)
						assert_float(b.end.y).override_failure_message("%s %s top %.1f, original %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 1.5, ob.end.y + 1.5)
					seen += 1
				node.queue_free()
	assert_int(seen).is_equal(27 * 3 * 2)


func test_placed_instances_get_their_detail_ranges() -> void:
	var node: Node3D = (load(BuildingV3.model_path("d_lightwall")) as PackedScene).instantiate()
	BuildingV3.set_lods(node)
	assert_float((node.find_child("lod0", true, false) as GeometryInstance3D).visibility_range_end).is_equal(BuildingV3.LOD_M)
	assert_float((node.find_child("lod1", true, false) as GeometryInstance3D).visibility_range_begin).is_equal(BuildingV3.LOD_M)
	node.free()


# --- industrial plants (LANCE-39): footprint, height and base y against the originals, three states, two LODs, library materials ---
const INDUSTRY := ["chemicalplant", "processingplant", "purificationplant", "wasteprocessor", "industrialplant", "industrialcomplex", "heavyindustrial",
	"factorysm", "factorymd", "factorylg", "powergenerator", "transformerstation", "valvestation", "relaystation", "straightpipe1", "straightpipe2",
	"straightpipe3", "cornerpipe", "endpipe", "threewaypipe", "fourwaypipe", "crane", "gantry"]


func _orig_aabb(n: Node) -> AABB:
	var out := AABB()
	var first := true
	for m in n.find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		if mi.mesh == null or mi.name.to_lower().begins_with("litwin"):  # the lit-window overlay is no part of the footprint
			continue
		var bb: AABB = (n.global_transform.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb()
		out = bb if first else out.merge(bb)
		first = false
	return out


func test_industrial_family_matches_the_originals_bounds_on_every_axis() -> void:
	for app in INDUSTRY:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _orig_aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var l := node.find_child(lod, true, false) as MeshInstance3D
				assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
				for i in l.mesh.get_surface_count():
					var mat := l.mesh.surface_get_material(i)
					var nm := mat.resource_name if mat else ""
					assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
						.override_failure_message("%s%s %s surface %d: '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
				if st != "":
					continue
				var b := l.mesh.get_aabb()
				var tol := 3.0
				assert_float(b.position.x).override_failure_message("%s %s x0 %.1f vs %.1f" % [app, lod, b.position.x, ob.position.x]).is_between(ob.position.x - tol, ob.position.x + tol)
				assert_float(b.end.x).override_failure_message("%s %s x1 %.1f vs %.1f" % [app, lod, b.end.x, ob.end.x]).is_between(ob.end.x - tol, ob.end.x + tol)
				assert_float(b.position.z).override_failure_message("%s %s z0 %.1f vs %.1f" % [app, lod, b.position.z, ob.position.z]).is_between(ob.position.z - tol, ob.position.z + tol)
				assert_float(b.end.z).override_failure_message("%s %s z1 %.1f vs %.1f" % [app, lod, b.end.z, ob.end.z]).is_between(ob.end.z - tol, ob.end.z + tol)
				assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 4.5, ob.end.y + 2.5)
				# base: on the ground like the original (a pit the original sinks into may stay on the ground)
				assert_float(b.position.y).override_failure_message("%s %s base y %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(minf(ob.position.y, 0.0) - 0.6, 0.6)
			node.queue_free()


# --- civilian and city buildings (LANCE-39): the same checks as the industrial family ---
const CITY := ["singlecivlivinga", "singlecivlivingb", "singlecivlivingc", "singlecivlivingd", "2civliving", "2storycivliving", "city2storya", "city2storyb",
	"city2storyc", "city4storya", "city4storyb", "city4storyc", "city6storya", "city6storyb", "city6storyc", "city8storya", "city8storyb", "city8storyc",
	"shack", "tinshack", "greenhouse", "barracks", "meethall"]


func test_city_family_matches_the_originals_bounds_on_every_axis() -> void:
	for app in CITY:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _orig_aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var l := node.find_child(lod, true, false) as MeshInstance3D
				assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
				for i in l.mesh.get_surface_count():
					var mat := l.mesh.surface_get_material(i)
					var nm := mat.resource_name if mat else ""
					assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
						.override_failure_message("%s%s %s surface %d: '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
				if st != "":
					continue
				var b := l.mesh.get_aabb()
				var tol := 3.0
				assert_float(b.position.x).override_failure_message("%s %s x0 %.1f vs %.1f" % [app, lod, b.position.x, ob.position.x]).is_between(ob.position.x - tol, ob.position.x + tol)
				assert_float(b.end.x).override_failure_message("%s %s x1 %.1f vs %.1f" % [app, lod, b.end.x, ob.end.x]).is_between(ob.end.x - tol, ob.end.x + tol)
				assert_float(b.position.z).override_failure_message("%s %s z0 %.1f vs %.1f" % [app, lod, b.position.z, ob.position.z]).is_between(ob.position.z - tol, ob.position.z + tol)
				assert_float(b.end.z).override_failure_message("%s %s z1 %.1f vs %.1f" % [app, lod, b.end.z, ob.end.z]).is_between(ob.end.z - tol, ob.end.z + tol)
				assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 4.5, ob.end.y + 2.5)
				assert_float(b.position.y).override_failure_message("%s %s base y %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(minf(ob.position.y, 0.0) - 0.6, 0.6)
			node.queue_free()


# --- military buildings (LANCE-39): bounds on every axis, as the city and industrial families ---
const MILITARY := ["s_hq", "l_gatecontrol", "lookouttower", "l_hq", "d_hq", "s_barracks", "s_barracks2", "l_elitebarracks", "l_guardhouse", "s_gatecontrol", "d_gatecontrol", "s_sensorcontrol", "l_sensorcontrol", "d_sensorcontrol", "s_spotlightcontrol", "l_spotlightcontrol", "sensortower", "prison", "weaponsfacility", "genericmilitary", "milcheckpoint", "perimeteralarm", "ammodump", "s_flag", "l_flag", "d_flag", "l_banner", "tent", "htent", "hqtent", "longtent", "camonetting", "streetlight", "crateswithtarp", "woodencrates", "barrels", "burningtrashbarrel", "hazmat", "dumpster", "geodesicdome", "munitionscrates", "lockers", "rpbuilding", "trafcon", "bridge", "motorcycle", "stopsign", "junkpile"]


func test_military_family_matches_the_originals_bounds_on_every_axis() -> void:
	for app in MILITARY:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _orig_aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var l := node.find_child(lod, true, false) as MeshInstance3D
				assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
				for i in l.mesh.get_surface_count():
					var mat := l.mesh.surface_get_material(i)
					var nm := mat.resource_name if mat else ""
					assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
						.override_failure_message("%s%s %s surface %d: '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
				if st != "":
					continue
				var b := l.mesh.get_aabb()
				var tol := 3.0
				assert_float(b.position.x).override_failure_message("%s %s x0 %.1f vs %.1f" % [app, lod, b.position.x, ob.position.x]).is_between(ob.position.x - tol, ob.position.x + tol)
				assert_float(b.end.x).override_failure_message("%s %s x1 %.1f vs %.1f" % [app, lod, b.end.x, ob.end.x]).is_between(ob.end.x - tol, ob.end.x + tol)
				assert_float(b.position.z).override_failure_message("%s %s z0 %.1f vs %.1f" % [app, lod, b.position.z, ob.position.z]).is_between(ob.position.z - tol, ob.position.z + tol)
				assert_float(b.end.z).override_failure_message("%s %s z1 %.1f vs %.1f" % [app, lod, b.end.z, ob.end.z]).is_between(ob.end.z - tol, ob.end.z + tol)
				assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 4.5, ob.end.y + 2.5)
				assert_float(b.position.y).override_failure_message("%s %s base y %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(minf(ob.position.y, 0.0) - 0.6, 0.6)
			node.queue_free()


# --- Steiner government / admin complex (LANCE-39): bounds on every axis (tools/art/v3/bld_steinergov.py) ---
const STEINER_GOV := ["s_main", "s_main_leftwing", "s_main_rightwing", "s_main_stairs", "s_admin_entry", "s_admin_wing", "s_admin_core", "s_adminquarter", "s_gov1", "s_gov2", "s_govresidence", "s_promenade", "s_quetragon"]


func test_steiner_gov_family_matches_the_originals_bounds_on_every_axis() -> void:
	for app in STEINER_GOV:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _orig_aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var l := node.find_child(lod, true, false) as MeshInstance3D
				assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
				for i in l.mesh.get_surface_count():
					var mat := l.mesh.surface_get_material(i)
					var nm := mat.resource_name if mat else ""
					assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
						.override_failure_message("%s%s %s surface %d: '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
				if st != "":
					continue
				var b := l.mesh.get_aabb()
				var tol := 3.0
				assert_float(b.position.x).override_failure_message("%s %s x0 %.1f vs %.1f" % [app, lod, b.position.x, ob.position.x]).is_between(ob.position.x - tol, ob.position.x + tol)
				assert_float(b.end.x).override_failure_message("%s %s x1 %.1f vs %.1f" % [app, lod, b.end.x, ob.end.x]).is_between(ob.end.x - tol, ob.end.x + tol)
				assert_float(b.position.z).override_failure_message("%s %s z0 %.1f vs %.1f" % [app, lod, b.position.z, ob.position.z]).is_between(ob.position.z - tol, ob.position.z + tol)
				assert_float(b.end.z).override_failure_message("%s %s z1 %.1f vs %.1f" % [app, lod, b.end.z, ob.end.z]).is_between(ob.end.z - tol, ob.end.z + tol)
				assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 4.5, ob.end.y + 2.5)
				assert_float(b.position.y).override_failure_message("%s %s base y %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(minf(ob.position.y, 0.0) - 0.6, 0.6)
			node.queue_free()


# --- Liao palace and residence family (LANCE-39): bounds on every axis, in the in-game frame the originals use (tools/art/v3/bld_liaopalace.py) ---
const LIAO_PALACE := ["l_palacetwr", "l_palacewing", "l_palacecore", "l_palacegate", "l_residencecore", "l_residenceleft", "l_residenceright"]


func test_liao_palace_family_matches_the_originals_bounds_on_every_axis() -> void:
	for app in LIAO_PALACE:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _orig_aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var l := node.find_child(lod, true, false) as MeshInstance3D
				assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
				for i in l.mesh.get_surface_count():
					var mat := l.mesh.surface_get_material(i)
					var nm := mat.resource_name if mat else ""
					assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
						.override_failure_message("%s%s %s surface %d: '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
				var b := l.mesh.get_aabb()
				var tol := 1.5
				assert_float(b.position.x).override_failure_message("%s%s %s x0 %.1f vs %.1f" % [app, st, lod, b.position.x, ob.position.x]).is_between(ob.position.x - (tol if st == "" else 3.5), ob.position.x + (tol if st == "" else 99.0))
				assert_float(b.end.x).override_failure_message("%s%s %s x1 %.1f vs %.1f" % [app, st, lod, b.end.x, ob.end.x]).is_between(ob.end.x - (tol if st == "" else 99.0), ob.end.x + (tol if st == "" else 3.5))
				assert_float(b.position.z).override_failure_message("%s%s %s z0 %.1f vs %.1f" % [app, st, lod, b.position.z, ob.position.z]).is_between(ob.position.z - (tol if st == "" else 3.5), ob.position.z + (tol if st == "" else 99.0))
				assert_float(b.end.z).override_failure_message("%s%s %s z1 %.1f vs %.1f" % [app, st, lod, b.end.z, ob.end.z]).is_between(ob.end.z - (tol if st == "" else 99.0), ob.end.z + (tol if st == "" else 3.5))
				if st == "":
					assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 2.5, ob.end.y + 2.5)
					assert_float(b.position.y).override_failure_message("%s %s base y %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(minf(ob.position.y, 0.0) - 0.6, 0.6)
				elif st == "_destroyed":
					assert_float(b.end.y).override_failure_message("%s_destroyed %s is %.1f m tall (rubble)" % [app, lod, b.end.y]).is_less(12.0)
			node.queue_free()


# --- Spaceport / airfield family (LANCE-39): bounds on every axis, wreck height, lamp materials (tools/art/v3/bld_spaceport.py). rpbuilding is in MILITARY above. ---
const SPACEPORT := ["terminal1", "terminal2", "lobby", "centerlobby", "hub", "walkway", "shuttle",
	"lifeboatcrashed", "lifeboatrusted", "runwaylight", "redbeaconlight", "bluebeaconlight", "greenbeaconlight"]


func test_spaceport_family_matches_the_originals_bounds_on_every_axis() -> void:
	for app in SPACEPORT:
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var ob := _orig_aabb(orig)
		orig.queue_free()
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			assert_str(p).override_failure_message("%s%s has no v3 model" % [app, st]).is_not_empty()
			var node: Node3D = (load(p) as PackedScene).instantiate()
			BuildingV3.set_lods(node)
			add_child(node)
			for lod in ["lod0", "lod1"]:
				var l := node.find_child(lod, true, false) as MeshInstance3D
				assert_object(l).override_failure_message("%s%s has no %s" % [app, st, lod]).is_not_null()
				for i in l.mesh.get_surface_count():
					var mat := l.mesh.surface_get_material(i)
					var nm := mat.resource_name if mat else ""
					assert_bool(nm.begins_with("bv3_") and BuildingV3.resolves(nm.trim_prefix("bv3_"))) \
						.override_failure_message("%s%s %s surface %d: '%s' is not a library material" % [app, st, lod, i, nm]).is_true()
				var b := l.mesh.get_aabb()
				if st == "_destroyed":  # a wreck stays inside the original's footprint plus a little, and low
					assert_float(b.end.y).override_failure_message("%s_destroyed %s is %.1f m tall" % [app, lod, b.end.y]).is_less(12.0)
					assert_float(b.position.x).override_failure_message("%s_destroyed %s x0 %.1f outside %.1f" % [app, lod, b.position.x, ob.position.x]).is_greater(ob.position.x - 3.0)
					assert_float(b.end.x).override_failure_message("%s_destroyed %s x1 %.1f outside %.1f" % [app, lod, b.end.x, ob.end.x]).is_less(ob.end.x + 3.0)
					assert_float(b.position.z).override_failure_message("%s_destroyed %s z0 %.1f outside %.1f" % [app, lod, b.position.z, ob.position.z]).is_greater(ob.position.z - 3.0)
					assert_float(b.end.z).override_failure_message("%s_destroyed %s z1 %.1f outside %.1f" % [app, lod, b.end.z, ob.end.z]).is_less(ob.end.z + 3.0)
				if st != "":
					continue
				var tol := 3.0
				assert_float(b.position.x).override_failure_message("%s %s x0 %.1f vs %.1f" % [app, lod, b.position.x, ob.position.x]).is_between(ob.position.x - tol, ob.position.x + tol)
				assert_float(b.end.x).override_failure_message("%s %s x1 %.1f vs %.1f" % [app, lod, b.end.x, ob.end.x]).is_between(ob.end.x - tol, ob.end.x + tol)
				assert_float(b.position.z).override_failure_message("%s %s z0 %.1f vs %.1f" % [app, lod, b.position.z, ob.position.z]).is_between(ob.position.z - tol, ob.position.z + tol)
				assert_float(b.end.z).override_failure_message("%s %s z1 %.1f vs %.1f" % [app, lod, b.end.z, ob.end.z]).is_between(ob.end.z - tol, ob.end.z + tol)
				assert_float(b.end.y).override_failure_message("%s %s top %.1f vs %.1f" % [app, lod, b.end.y, ob.end.y]).is_between(ob.end.y - 4.5, ob.end.y + 2.5)
				assert_float(b.position.y).override_failure_message("%s %s base y %.1f vs %.1f" % [app, lod, b.position.y, ob.position.y]).is_between(minf(ob.position.y, 0.0) - 0.6, 0.6)
			node.queue_free()


func test_spaceport_lamps_glow_until_destroyed() -> void:
	for app in ["runwaylight", "redbeaconlight", "bluebeaconlight", "greenbeaconlight"]:
		for st in ["", "_damaged", "_destroyed"]:
			var node: Node3D = (load(BuildingV3.model_path(app, st)) as PackedScene).instantiate()
			var lod0 := node.find_child("lod0", true, false) as MeshInstance3D
			var has_lamp := false
			var has_halo := false
			for i in lod0.mesh.get_surface_count():
				var nm := lod0.mesh.surface_get_material(i).resource_name
				has_lamp = has_lamp or (nm.begins_with("bv3_lamp_") and nm != "bv3_lamp_off")
				has_halo = has_halo or nm.begins_with("bv3_halo_")
			assert_bool(has_lamp).override_failure_message("%s%s: emissive lamp lens expected: %s" % [app, st, st != "_destroyed"]).is_equal(st != "_destroyed")
			assert_bool(has_halo).override_failure_message("%s%s: halo expected only when intact" % [app, st]).is_equal(st == "")
			node.free()
