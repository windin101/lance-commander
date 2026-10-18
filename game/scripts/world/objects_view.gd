class_name ObjectsView
extends Node3D
## Placed map objects (trees, buildings, props) from data/maps/<mission>/objects.json.
## Object rotation uses the same convention as unit facing. Destroyed buildings
## swap to their damaged model (<appearance>_dam.glb) or collapse into the ground.

var nodes: Dictionary = {}  # object index -> Node3D
var _appearance: Dictionary = {}  # object index -> appearance name


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
		if not scenes.has(app):
			var res := "res://assets/objects/%s.glb" % app
			scenes[app] = load(res) if ResourceLoader.exists(res) else null
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
	return placed


func destroy(index: int) -> void:
	var node: Node3D = nodes.get(index)
	if node == null:
		return
	var dam := "res://assets/objects/%s_dam.glb" % _appearance[index]
	if ResourceLoader.exists(dam):
		var wreck: Node3D = load(dam).instantiate()
		wreck.transform = node.transform
		add_child(wreck)
		node.queue_free()
		nodes[index] = wreck
	else:
		node.scale = Vector3(1.0, 0.25, 1.0)  # no damaged model: flatten the ruin
