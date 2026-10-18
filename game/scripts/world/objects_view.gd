class_name ObjectsView
extends Node3D
## Placed map objects (trees, buildings, props) from data/maps/<mission>/objects.json.
## Object rotation uses the same convention as unit facing.


func build(sim_map: SimMap, mission: String) -> int:
	var path := "res://data/maps/%s/objects.json" % mission
	if not FileAccess.file_exists(path):
		return 0
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var types: Dictionary = data["types"]
	var scenes := {}
	var placed := 0
	for o in data["objects"]:
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
		placed += 1
	return placed
