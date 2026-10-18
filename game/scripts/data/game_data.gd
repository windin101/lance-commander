extends Node
## Read-only access to the converted MC2 data in res://data (see tools/convert).
## Godot's JSON parser returns every number as a float; tables are used as-is and
## callers cast with int() where the original used integers.

var components: Dictionary = {}  # id (int) -> component
var chassis: Dictionary = {}  # file stem -> chassis
var gamesys: Dictionary = {}
var heat_table: Array = []
var strings: Dictionary = {}  # id (String) -> text


func _ready() -> void:
	load_all()


func load_all() -> void:
	components.clear()
	for c in _read("res://data/components.json"):
		components[int(c["id"])] = c
	chassis.clear()
	for file in DirAccess.get_files_at("res://data/chassis"):
		if file.ends_with(".json"):
			chassis[file.get_basename()] = _read("res://data/chassis/" + file)
	gamesys = _read("res://data/gamesys.json")
	heat_table = _read("res://data/heat.json")
	strings = _read("res://data/strings.json")


func string(id: int) -> String:
	return strings.get(str(id), "")


func _read(path: String) -> Variant:
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		push_error("GameData: missing or empty %s" % path)
		return {}
	var data: Variant = JSON.parse_string(text)
	if data == null:
		push_error("GameData: bad JSON in %s" % path)
	return data
