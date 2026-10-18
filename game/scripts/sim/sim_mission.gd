class_name SimMission
extends RefCounted
## Builds a SimWorld from a converted mission FIT: terrain, then every Part
## whose chassis has a stats CSV (mechs). Other parts (vehicles, infantry)
## are listed in `skipped` until their rules exist.

const WORLD_UNIT_M := 0.2

var world: SimWorld
var skipped: Array[String] = []
var player_team := 0


static func load_mission(data: Object, mission: String, seed_value: int = 1) -> SimMission:
	var sm := SimMission.new()
	var fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % mission))
	var map := SimMap.load_mission(mission)
	map.forest_cost = float(data.gamesys["General"].get("ForestMoveCost", 50))
	var rules := SimRules.from_data(data)
	sm.world = SimWorld.new(rules, map, seed_value)
	sm.player_team = int(fit.get("Player0", {}).get("DefaultTeam", 0))
	var num_parts := int(fit.get("Parts", {}).get("NumParts", 0))
	for i in range(1, num_parts + 1):
		var part: Dictionary = fit.get("Part%d" % i, {})
		if part.is_empty():
			continue
		var chassis_key := String(part.get("CSVFile", "")).to_lower()
		if not data.chassis.has(chassis_key):
			sm.skipped.append(String(part.get("CSVFile", "?")))
			continue
		var warrior: Dictionary = fit.get("Warrior%d" % int(part.get("Pilot", i)), {})
		var pilot_fit: Dictionary = data.pilots.get(String(warrior.get("Profile", "")).to_lower(), {})
		var pilot := SimPilot.from_fit(pilot_fit) if not pilot_fit.is_empty() else SimPilot.make(50, 50)
		var m := SimMech.from_chassis(data.chassis[chassis_key], int(part.get("VariantNumber", 0)), rules, pilot)
		m.model = chassis_key
		m.team = int(part.get("TeamID", 0))
		m.is_player = m.team == sm.player_team
		m.position = Vector2(float(part["PositionX"]), float(part["PositionY"])) * WORLD_UNIT_M
		m.facing = float(part.get("Rotation", 0.0))
		m.paint = [int(part.get("HighlightColor1", -1)), int(part.get("HighlightColor2", -1)), int(part.get("BaseColor", -1))]
		_apply_model_speeds(m)
		sm.world.add_mech(m)
	return sm


## Walk speed from the model sidecar's walk gesture (m/s), when converted.
static func _apply_model_speeds(m: SimMech) -> void:
	var path := "res://assets/mechs/%s.json" % m.model
	if not FileAccess.file_exists(path):
		return
	var side: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	for g in side.get("gestures", []):
		if g["id"] == "walk" and float(g["end_velocity"]) > 0.0:
			m.walk_speed = float(g["end_velocity"])
