class_name ObjectsView
extends Node3D
## Placed map objects (trees, buildings, props) from data/maps/<mission>/objects.json.
## Object rotation uses the same convention as unit facing. Destroyed buildings
## swap to their damaged model (<appearance>_dam.glb) or collapse into the ground.

var nodes: Dictionary = {}  # object index -> Node3D
var _appearance: Dictionary = {}  # object index -> appearance name
# HD trees (tools/art/trees.py): every tree of one appearance is one MultiMesh for its bark and one for its
# leaves. --no-hd keeps the original cards.
var _trees_on := not OS.get_cmdline_user_args().has("--no-hd")
var _tree_xf: Dictionary = {}     # appearance -> Array[Transform3D]
var _tree_slot: Dictionary = {}   # object index -> [appearance, instance]
var _tree_mm: Dictionary = {}     # appearance -> [bark MultiMesh, leaves MultiMesh]


func build(sim_map: SimMap, mission: String) -> int:
	var path := "res://data/maps/%s/objects.json" % mission
	if not FileAccess.file_exists(path):
		return 0
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var types: Dictionary = data["types"]
	var scenes := {}
	var placed := 0
	for index in data["objects"].size():
		var o: Dictionary = data["objects"][index]
		var t: Dictionary = types.get(str(int(o["type"])), {})
		var app: String = t.get("appearance", "")
		if app.is_empty():
			continue
		if _trees_on and ResourceLoader.exists("res://assets/trees/%s.glb" % app):
			_add_tree(app, index, o, sim_map)  # HD trees: drawn in batches (MultiMesh), see _build_trees
			_appearance[index] = app
			placed += 1
			continue
		if not scenes.has(app):
			# HD models (tools/art, --kind objects) replace the 2001 mesh when present; --no-hd compares.
			# order: the SolidCraft rebuild, then an HD model (a licensed sculpt, or Hunyuan), then the original model with 4x
			# upscaled textures (tools/art/upscale_textures.py), then the original
			var res := BuildingV3.model_path(app)  # v3: procedural model on the shared PBR library (tools/art/v3/bld_*.py)
			if res == "":
				res = ArtV2.model_path("objects", app)  # HD rework (tools/art/hd_v2_building.py), dev switch
			if res == "":
				res = "res://assets/objects/%s_cad.glb" % app  # SolidCraft rebuild (tools/cad, tools/art/cad_building.py)
			if not ResourceLoader.exists(res):  # a licensed sculpt or HD model beats the upscaled original (7 aircraft props)
				res = "res://assets/objects/%s_hd.glb" % app
			if not ResourceLoader.exists(res):
				res = "res://assets/objects/%s_hdtex.glb" % app
			if not ResourceLoader.exists(res) or OS.get_cmdline_user_args().has("--no-hd"):
				res = "res://assets/objects/%s.glb" % app
			scenes[app] = load(res) if ResourceLoader.exists(res) else null
			if scenes[app] != null:
				var probe: Node3D = scenes[app].instantiate()
				_matte(probe)  # materials are shared by every instance of this model
				if res.begins_with("res://assets/v3/objects/"):
					BuildingV3.dress(probe)
				if res.begins_with("res://assets/v2/"):
					ArtV2.dress_object(probe, app)
				probe.free()
		if scenes[app] == null:
			continue
		var node: Node3D = _vehicle_prop(app, false) if (BuildingV3.enabled and BuildingV3.PROP_VEHICLES.has(app)) else null
		if node == null and BuildingV3.enabled and MechPieces.KINDS.has(app):
			node = MechPieces.piece(app, index)
		if node == null:
			node = scenes[app].instantiate()
		BuildingV3.set_lods(node)
		var pos := Vector2(float(o["x"]), float(o["y"])) * sim_map.meters_per_wu
		node.position = TerrainView.to_3d(pos, sim_map.height_at(pos))
		node.rotation.y = PI - deg_to_rad(float(o["rotation"]))
		add_child(node)
		nodes[index] = node
		_appearance[index] = app
		placed += 1
	_build_trees()
	_dev_force_state()
	return placed


## Dev only (art review): --bld-state=damaged|destroyed --bld-app=a,b puts every placed building of those appearances in that state at load.
func _dev_force_state() -> void:
	var st := ""
	var apps := PackedStringArray()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--bld-state="):
			st = a.split("=")[1]
		elif a.begins_with("--bld-app="):
			apps = a.split("=")[1].split(",")
	if st == "":
		return
	for index in nodes.keys():
		if String(_appearance.get(index, "")) in apps:
			if st == "destroyed":
				destroy(index)
			else:
				set_damage(index, 0.6)


## World-space bounds of map object `index` (for blast sizes); empty if it has no node (trees: a small box).
func bounds(index: int) -> AABB:
	if _tree_slot.has(index):
		var slot: Array = _tree_slot[index]
		var xf: Transform3D = _tree_xf[slot[0]][slot[1]]
		return AABB(xf.origin - Vector3(2, 0, 2), Vector3(4, 8, 4))
	var node: Node3D = nodes.get(index)
	if node == null:
		return AABB()
	var box := AABB()
	var first := true
	for mi in node.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if m.mesh == null:
			continue
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


var _turret_heads: Dictionary = {}  # object index -> [the model's "Turret" node, its rest transform, placement yaw]


## Turn a map turret's gun (the shape's "Turret" node, Gvactor/bdactor setMoverParameters) to an
## absolute heading in degrees (0 = north, clockwise).
func set_turret_yaw(index: int, yaw_deg: float, placed_deg: float) -> void:
	if not _turret_heads.has(index):
		var node: Node3D = nodes.get(index)
		var head: Node3D = node.find_child("Turret", true, false) as Node3D if node else null
		_turret_heads[index] = [head, head.transform if head else Transform3D(), placed_deg]
	var h: Array = _turret_heads[index]
	if h[0] == null or not is_instance_valid(h[0]):
		return
	var rest: Transform3D = h[1]
	(h[0] as Node3D).transform = Transform3D(Basis(Vector3.UP, -deg_to_rad(yaw_deg - float(h[2]))) * rest.basis, rest.origin)


## Pop-up emplacements (v3 models with a `Pop` node, bld_turrets.py): the two door leaves (pop_door_l / pop_door_r, hinged at their
## outer edges) swing up, then the lift (`Pop`) raises the turret POP_RISE_M over the rest of POP_TIME, as the sim's pop-up gesture
## (SimTurret.can_fire_time) opens; closing plays it backwards. f: 0 closed .. 1 open, the first POP_DOOR_FRAC of it the doors.
const POP_RISE_M := 8.4
const POP_DOOR_DEG := 100.0
const POP_DOOR_FRAC := 0.3
const POP_TIME := 1.5
var _pop: Dictionary = {}  # object index -> [Pop node or null, rest y, [door nodes], open (bool), tween, progress f]


func _pop_rig(index: int) -> Array:
	if not _pop.has(index):
		var node: Node3D = nodes.get(index)
		var pop: Node3D = node.find_child("Pop", true, false) as Node3D if node else null
		var doors: Array = []
		if node:
			for nm in ["pop_door_l", "pop_door_r"]:
				var d := node.find_child(nm, true, false) as Node3D
				if d:
					doors.append(d)
		_pop[index] = [pop, pop.position.y if pop else 0.0, doors, false, null, 0.0]
	return _pop[index]


## The sim popped the turret up (open) or put it away.
func set_turret_pop(index: int, open: bool) -> void:
	var rig := _pop_rig(index)
	if rig[0] == null or bool(rig[3]) == open:
		return
	rig[3] = open
	if rig[4] != null and (rig[4] as Tween).is_valid():
		(rig[4] as Tween).kill()
	var f0 := pop_progress(index)
	var tw := create_tween()
	tw.tween_method(_apply_pop.bind(index), f0, 1.0 if open else 0.0, POP_TIME * absf((1.0 if open else 0.0) - f0))
	rig[4] = tw


## Where the pop-up is now, 0 closed .. 1 open.
func pop_progress(index: int) -> float:
	return float(_pop_rig(index)[5])


func _apply_pop(f: float, index: int) -> void:
	var rig := _pop_rig(index)
	if rig[0] == null:
		return
	var door := clampf(f / POP_DOOR_FRAC, 0.0, 1.0)
	var rise := clampf((f - POP_DOOR_FRAC) / (1.0 - POP_DOOR_FRAC), 0.0, 1.0)
	rise = rise * rise * (3.0 - 2.0 * rise)
	for d in rig[2]:
		(d as Node3D).rotation.z = deg_to_rad(POP_DOOR_DEG) * door * (1.0 if (d as Node3D).name == "pop_door_l" else -1.0)
	(rig[0] as Node3D).position.y = float(rig[1]) + POP_RISE_M * rise
	rig[5] = f


func destroy(index: int) -> void:
	_pop.erase(index)
	_turret_heads.erase(index)
	if _tree_slot.has(index):  # a destroyed tree: the leaves go and the trunk is broken off to a stump
		var slot: Array = _tree_slot[index]
		var mms: Array = _tree_mm.get(slot[0], [])
		if mms.size() == 2:
			var xf: Transform3D = _tree_xf[slot[0]][slot[1]]
			var stump := Transform3D(xf.basis * Basis.from_scale(Vector3(1.4, 0.12, 1.4)), xf.origin)
			if mms[0]: (mms[0] as MultiMesh).set_instance_transform(slot[1], stump)
			if mms[1]: (mms[1] as MultiMesh).set_instance_transform(slot[1], Transform3D(Basis.from_scale(Vector3.ZERO), xf.origin))
		return
	var node: Node3D = nodes.get(index)
	if node == null:
		return
	if BuildingV3.enabled and BuildingV3.PROP_VEHICLES.has(_appearance[index]):
		var vw := _vehicle_prop(_appearance[index], true)
		if vw != null:
			vw.transform = node.transform
			add_child(vw)
			node.queue_free()
			nodes[index] = vw
			return
	var dam := BuildingV3.model_path(_appearance[index], "_destroyed")  # v3 wreck, else the original's damaged model
	if dam == "":
		dam = "res://assets/objects/%s_dam_hdtex.glb" % _appearance[index]
		if not ResourceLoader.exists(dam) or OS.get_cmdline_user_args().has("--no-hd"):
			dam = "res://assets/objects/%s_dam.glb" % _appearance[index]
	if ResourceLoader.exists(dam):
		var wreck: Node3D = _instance_state(dam)
		wreck.transform = node.transform
		add_child(wreck)
		node.queue_free()
		nodes[index] = wreck
	else:
		node.scale = Vector3(1.0, 0.25, 1.0)  # no damaged model: flatten the ruin


## A gate opens or closes: its door leaves (glTF nodes door_l, door_r of a v3 gate model) slide along z into the wall (bld_gates.py).
const GATE_SLIDE_M := 6.9


func set_gate_open(index: int, open: bool) -> void:
	var node: Node3D = nodes.get(index)
	if node == null:
		return
	for nm in ["door_l", "door_r"]:
		var leaf := node.find_child(nm, true, false) as Node3D
		if leaf == null:
			continue
		var target := (-GATE_SLIDE_M if nm == "door_l" else GATE_SLIDE_M) if open else 0.0
		create_tween().tween_property(leaf, "position:z", target, 1.4)


## A v3 model dressed once (its meshes are shared), or the plain scene for any other path.
func _instance_state(path: String) -> Node3D:
	var node: Node3D = (load(path) as PackedScene).instantiate()
	BuildingV3.set_lods(node)
	if path.begins_with("res://assets/v3/objects/") and not _dressed.has(path):
		BuildingV3.dress(node)
		_dressed[path] = true
	return node


## A vehicle prop drawn with the committed v3 vehicle model (static, no rig): the model stood on the ground (its wheels' lowest point at y 0), painted
## civilian yellow or drab military olive; wreck=true gives the vehicle's v3 wreck. Null when the vehicle model is missing (the original prop is used).
const MILITARY_PROPS := ["jeepprop", "armoredcarprop", "trooptransportprop", "ordnancetruckprop", "dunebuggyprop"]


func _vehicle_prop(app: String, wreck: bool) -> Node3D:
	var vname: String = BuildingV3.PROP_VEHICLES[app]
	var path := ArtV3.model_path("vehicles", vname + ("_wreck" if wreck else ""))
	if path == "":
		return null
	var inst: Node3D = (load(path) as PackedScene).instantiate()
	var scheme: Dictionary = {"mode": "mask", "base": "#5f6a46", "hl1": "#9a8a5a", "hl2": "#3a3f33"} if app in MILITARY_PROPS else PaintScheme.named("civilian")
	if wreck:  # a parked prop's wreck keeps the hull and nearby parts only: fragments are clipped to the prop's own footprint plus 20 %
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		var fp := AABB()
		var first := true
		for m in orig.find_children("*", "MeshInstance3D", true, false):
			var mi0 := m as MeshInstance3D
			if mi0.mesh:
				var b0 := MechPieces.rel_transform(mi0, orig) * mi0.mesh.get_aabb()
				fp = b0 if first else fp.merge(b0)
				first = false
		orig.free()
		fp = fp.grow(0.0)
		fp.position -= Vector3(fp.size.x * 0.1, 0.0, fp.size.z * 0.1)
		fp.size += Vector3(fp.size.x * 0.2, 0.0, fp.size.z * 0.2)
		for m in inst.find_children("*", "MeshInstance3D", true, false):
			var mi1 := m as MeshInstance3D
			if mi1.mesh == null:
				continue
			var c := (MechPieces.rel_transform(mi1, inst) * mi1.mesh.get_aabb()).get_center()
			if String(mi1.name).begins_with("debris") or c.x < fp.position.x or c.x > fp.end.x or c.z < fp.position.z or c.z > fp.end.z:
				mi1.visible = false
	ArtV3.apply(inst, vname, scheme, "vehicles")
	var low := 1e9
	for m in inst.find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		if mi.mesh and mi.visible:
			low = minf(low, (MechPieces.rel_transform(mi, inst) * mi.mesh.get_aabb()).position.y)
	inst.position.y = -low if low < 1e8 else 0.0
	var root := Node3D.new()
	root.add_child(inst)
	return root


var _dressed: Dictionary = {}  # v3 model path -> its meshes carry the library materials
var _hurt: Dictionary = {}     # object index -> true once its damaged state is showing


## A structure has taken damage: at half its damage level a building with a v3 damaged state swaps to it (the
## destroyed state follows through destroy()). frac = damage / damage_level.
func set_damage(index: int, frac: float) -> void:
	if frac < 0.5 or _hurt.has(index) or _tree_slot.has(index):
		return
	var node: Node3D = nodes.get(index)
	if node == null or not _appearance.has(index):
		return
	var path := BuildingV3.model_path(_appearance[index], "_damaged")
	if path == "":
		return
	_hurt[index] = true
	var hurt := _instance_state(path)
	hurt.transform = node.transform
	add_child(hurt)
	node.queue_free()
	nodes[index] = hurt
	_turret_heads.erase(index)  # the new model has its own Turret node: set_turret_yaw looks it up again
	if _pop.has(index):  # a pop-up damaged mid-gesture: the new model takes over the pose and the running tween
		var old: Array = _pop[index]
		_pop.erase(index)
		var rig := _pop_rig(index)
		rig[3] = old[3]
		rig[4] = old[4]
		_apply_pop(float(old[5]), index)


## The original lit map objects with the sun and ambient only (no specular, bdactor.cpp:4046-4120). Under the
## linear tone curve a glTF material's default specular blows sunlit tree tops out to white, so map objects
## are made matte.
static func _matte(n: Node) -> void:
	if n is MeshInstance3D and n.mesh:
		for i in n.mesh.get_surface_count():
			var m: Material = n.mesh.surface_get_material(i)
			if m is BaseMaterial3D:
				m.metallic_specular = 0.0
				m.metallic = 0.0
				m.roughness = 1.0
	for c in n.get_children():
		_matte(c)


func _add_tree(app: String, index: int, o: Dictionary, sim_map: SimMap) -> void:
	var pos := Vector2(float(o["x"]), float(o["y"])) * sim_map.meters_per_wu
	var jitter := 0.92 + 0.16 * fposmod(sin(float(index) * 12.9898) * 43758.5453, 1.0)  # a little size variety
	var basis := Basis(Vector3.UP, PI - deg_to_rad(float(o["rotation"]))).scaled(Vector3.ONE * jitter)
	var xf := Transform3D(basis, TerrainView.to_3d(pos, sim_map.height_at(pos)))
	if not _tree_xf.has(app):
		_tree_xf[app] = []
	_tree_slot[index] = [app, (_tree_xf[app] as Array).size()]
	(_tree_xf[app] as Array).append(xf)


static var _leaf_mat: ShaderMaterial
static var _bark_mat: StandardMaterial3D


func _build_trees() -> void:
	if _tree_xf.is_empty():
		return
	if _leaf_mat == null:
		_leaf_mat = ShaderMaterial.new()
		_leaf_mat.shader = load("res://shaders/leaves.gdshader")
		_leaf_mat.set_shader_parameter("leaf_atlas", load("res://assets/trees/leaves.png"))
		_bark_mat = StandardMaterial3D.new()
		_bark_mat.albedo_texture = load("res://assets/trees/bark.png")
		_bark_mat.vertex_color_use_as_albedo = true
		_bark_mat.roughness = 1.0
		_bark_mat.metallic_specular = 0.0
		_bark_mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	for app in _tree_xf:
		var scene: Node3D = load("res://assets/trees/%s.glb" % app).instantiate()
		var pair: Array = [null, null]
		for k in 2:
			var mi := scene.find_child(["bark", "leaves"][k], true, false) as MeshInstance3D
			if mi == null:
				continue
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = mi.mesh
			var xfs: Array = _tree_xf[app]
			mm.instance_count = xfs.size()
			for i in xfs.size():
				mm.set_instance_transform(i, xfs[i])
			var inst := MultiMeshInstance3D.new()
			inst.name = "%s_%s" % [app, ["bark", "leaves"][k]]
			inst.multimesh = mm
			inst.material_override = _bark_mat if k == 0 else _leaf_mat
			add_child(inst)
			pair[k] = mm
		_tree_mm[app] = pair
		scene.free()
