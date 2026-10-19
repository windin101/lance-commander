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
			# order: the original model with 4x upscaled textures (tools/art/upscale_textures.py), then a
			# Hunyuan HD model, then the original
			var res := "res://assets/objects/%s_hdtex.glb" % app
			if not ResourceLoader.exists(res):
				res = "res://assets/objects/%s_hd.glb" % app
			if not ResourceLoader.exists(res) or OS.get_cmdline_user_args().has("--no-hd"):
				res = "res://assets/objects/%s.glb" % app
			scenes[app] = load(res) if ResourceLoader.exists(res) else null
			if scenes[app] != null:
				var probe: Node3D = scenes[app].instantiate()
				_matte(probe)  # materials are shared by every instance of this model
				probe.free()
		if scenes[app] == null:
			continue
		var node: Node3D = scenes[app].instantiate()
		var pos := Vector2(float(o["x"]), float(o["y"])) * sim_map.meters_per_wu
		node.position = TerrainView.to_3d(pos, sim_map.height_at(pos))
		node.rotation.y = PI - deg_to_rad(float(o["rotation"]))
		add_child(node)
		nodes[index] = node
		_appearance[index] = app
		placed += 1
	_build_trees()
	return placed


func destroy(index: int) -> void:
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
	var dam := "res://assets/objects/%s_dam_hdtex.glb" % _appearance[index]
	if not ResourceLoader.exists(dam) or OS.get_cmdline_user_args().has("--no-hd"):
		dam = "res://assets/objects/%s_dam.glb" % _appearance[index]
	if ResourceLoader.exists(dam):
		var wreck: Node3D = load(dam).instantiate()
		wreck.transform = node.transform
		add_child(wreck)
		node.queue_free()
		nodes[index] = wreck
	else:
		node.scale = Vector3(1.0, 0.25, 1.0)  # no damaged model: flatten the ruin


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
