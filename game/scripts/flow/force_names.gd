class_name ForceNames
extends RefCounted
## Display names of the mission forces (Phase 8): a unit's mission colour triple
## [HighlightColor1, HighlightColor2, BaseColor] -> its faction in res://data/faction_paint.json
## (tools/art/faction_paint.py) -> that faction scheme's display_name ("Davion Regiment",
## "Steiner Guards", "Liao Armored Cavalry", "Bandit Legion"). Unmapped triples give "".

static var _data := {}


static func _table() -> Dictionary:
	if _data.is_empty():
		var p := "res://data/faction_paint.json"
		var d = JSON.parse_string(FileAccess.get_file_as_string(p)) if FileAccess.file_exists(p) else null
		_data = d if d is Dictionary else {"triples": {}, "schemes": {}}
	return _data


static func _hex(v: int) -> String:
	return "#%06x" % (v & 0xFFFFFF)


## The faction key ("davion", "steiner", "liao", "bandits") of a colour triple, or "".
static func faction(paint: Array) -> String:
	if paint.size() != 3:
		return ""
	var key := "%s|%s|%s" % [_hex(int(paint[2])), _hex(int(paint[0])), _hex(int(paint[1]))]  # base|hl1|hl2, as the table
	return String(_table().get("triples", {}).get(key, {}).get("faction", ""))


## The force's display name for a colour triple, or "".
static func for_paint(paint: Array) -> String:
	var f := faction(paint)
	if f == "":
		return ""
	return String(_table().get("schemes", {}).get(f, {}).get("display_name", ""))


## A mission unit's force name ("" for the player's own lance and unmapped colours).
static func of_unit(u: SimUnit) -> String:
	if u == null or (u.is_player and u.commander == 0):
		return ""
	return for_paint(u.paint)
