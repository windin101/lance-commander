class_name MissionBrief
extends RefCounted
## What the briefing screen shows, built from a converted mission: title, the two
## briefing texts, objectives with their map markers, and the player lance.

var mission := ""
var title := ""
var summary := ""  # MissionSettings Blurb2: one line
var blurb := ""  # MissionSettings Blurb: the full briefing, incl. "Tactical Officer Notes"
var objectives: Array[Dictionary] = []  # {index, title, primary, hidden, marker: Vector2 (m) or null}
var lance: Array[Dictionary] = []  # {chassis, variant, tonnage, pilot, callsign}
var map_half_m := 0.0
var map_image := ""  # res:// path of the mission's colour map
var available := false

const WU := 0.2


static func load_mission(data: Object, mission_name: String) -> MissionBrief:
	var b := MissionBrief.new()
	b.mission = mission_name
	var path := "res://data/missions/%s.json" % mission_name
	b.available = FileAccess.file_exists(path)
	if not b.available:
		b.title = mission_name
		return b
	var fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var ms: Dictionary = fit.get("MissionSettings", {})
	b.title = _text(data, ms, "MissionName")
	b.summary = _text(data, ms, "Blurb2")
	b.blurb = _text(data, ms, "Blurb")
	var count := int(fit.get("Team0Objectives", {}).get("NumObjectives", 0))
	for i in range(count if count > 0 else 32):
		var o: Dictionary = fit.get("Team0Objective%d" % i, {})
		if o.is_empty():
			if count > 0:
				continue
			break
		var marker = null
		if o.get("DisplayMarker", false):
			marker = Vector2(float(o.get("MarkerX", 0.0)), float(o.get("MarkerY", 0.0))) * WU
		b.objectives.append({"index": i, "title": _text(data, o, "Title").strip_edges(),
			"primary": int(o.get("Priority", 1)) == 1, "hidden": bool(o.get("HiddenTrigger", false)), "marker": marker})
	var parts := int(fit.get("Parts", {}).get("NumParts", 0))
	for i in range(1, parts + 1):
		var p: Dictionary = fit.get("Part%d" % i, {})
		if not p.get("PlayerPart", false):
			continue
		var key := String(p.get("CSVFile", "")).to_lower()
		var ch: Dictionary = data.chassis.get(key, {})
		var variant := int(p.get("VariantNumber", 0))
		var vname := ""
		var variants: Array = ch.get("variants", [])
		if variant < variants.size():
			vname = String(variants[variant].get("name", ""))
		var w: Dictionary = fit.get("Warrior%d" % int(p.get("Pilot", i)), {})
		var pilot: Dictionary = data.pilots.get(String(w.get("Profile", "")).to_lower(), {}).get("General", {})
		b.lance.append({"chassis": String(ch.get("name", key.capitalize())), "variant": vname,
			"tonnage": float(ch.get("tonnage", 0.0)), "pilot": String(pilot.get("Name", "")),
			"callsign": String(pilot.get("Callsign", ""))})
	var terrain_path := "res://data/maps/%s/terrain.json" % mission_name
	if FileAccess.file_exists(terrain_path):
		var t: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(terrain_path))
		b.map_half_m = float(t.get("vertices_per_side", 0)) * float(t.get("world_units_per_vertex", 0)) * float(t.get("meters_per_world_unit", WU)) / 2.0
	b.map_image = "res://assets/maps/%s/burnin.jpg" % mission_name
	return b


## A FIT text field: the resource string when it says so, else the literal text.
static func _text(data: Object, block: Dictionary, key: String) -> String:
	if block.get(key + "UseResourceString", false):
		var s: String = data.string(int(block.get(key + "ResourceStringID", 0)))
		if s != "":
			return UiStyle.clean(s)
	return UiStyle.clean(String(block.get(key, "")))


func visible_objectives() -> Array[Dictionary]:
	return objectives.filter(func(o): return not o["hidden"])
