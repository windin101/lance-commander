class_name SimMission
extends RefCounted
## Builds a SimWorld from a converted mission FIT: terrain, every Part whose
## chassis has a stats CSV (mechs), and the map's destructible buildings
## (object class 1 with a DmgLevel). Parts without rules yet are listed in
## `skipped`.

const WORLD_UNIT_M := 0.2

var world: SimWorld
var objectives: SimObjectives
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
	var vehicle_files: Dictionary = {}
	var vmap_path := "res://data/missions/%s_vehicles.json" % mission
	if FileAccess.file_exists(vmap_path):
		vehicle_files = JSON.parse_string(FileAccess.get_file_as_string(vmap_path))
	for i in range(1, num_parts + 1):
		var part: Dictionary = fit.get("Part%d" % i, {})
		if part.is_empty():
			continue
		var chassis_key := String(part.get("CSVFile", "")).to_lower()
		var warrior: Dictionary = fit.get("Warrior%d" % int(part.get("Pilot", i)), {})
		var pilot_fit: Dictionary = data.pilots.get(String(warrior.get("Profile", "")).to_lower(), {})
		var pilot := SimPilot.from_fit(pilot_fit) if not pilot_fit.is_empty() else SimPilot.make(50, 50)
		var m: SimUnit
		if data.chassis.has(chassis_key):
			m = SimMech.from_chassis(data.chassis[chassis_key], int(part.get("VariantNumber", 0)), rules, pilot)
			m.model = chassis_key
		elif vehicle_files.has(chassis_key):
			var vpath := "res://data/vehicles/%s.json" % vehicle_files[chassis_key]
			m = SimVehicle.from_data(JSON.parse_string(FileAccess.get_file_as_string(vpath)), rules, pilot)
		else:
			sm.skipped.append(String(part.get("CSVFile", "?")))
			continue
		m.brain_name = String(warrior.get("Brain", ""))
		m.team = int(part.get("TeamID", 0))
		m.is_player = m.team == sm.player_team
		m.position = Vector2(float(part["PositionX"]), float(part["PositionY"])) * WORLD_UNIT_M
		m.facing = float(part.get("Rotation", 0.0))
		m.paint = [int(part.get("HighlightColor1", -1)), int(part.get("HighlightColor2", -1)), int(part.get("BaseColor", -1))]
		if m is SimMech:
			_apply_model_speeds(m)
		m.part_index = i
		m.commander = int(part.get("CommanderID", m.team))
		sm.world.add_unit(m)
	sm._add_structures(mission)
	sm.objectives = SimObjectives.from_fit(fit, sm)
	sm.world.flags = sm.objectives.flags
	sm._attach_brains(mission)
	return sm


var script_cfg: Dictionary = {}
var _damage_watch: Array = []  # [{structure, flag}]


func _attach_brains(mission: String) -> void:
	var path := "res://data/brains/%s.json" % mission
	if not FileAccess.file_exists(path):
		return
	var cfg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var brains: Dictionary = cfg.get("brains", {})
	for u in world.units:
		if u.brain_name != "" and brains.has(u.brain_name):
			u.brain = SimBrain.create(brains[u.brain_name], u)
			if brains[u.brain_name].get("player", false):
				u.engage_m = float(brains[u.brain_name].get("engage_m", 0.0))
	script_cfg = cfg.get("script", {})
	for w in script_cfg.get("structure_damage_flags", []):
		var s := structure_near(Vector2(w["position"][0], w["position"][1]))
		if s:
			_damage_watch.append({"structure": s, "flag": String(w["flag"])})


## Advance the world one tick, evaluate objectives and the mission script;
## objective events join world.events.
func step() -> void:
	world.step()
	var ev := objectives.update(world)
	for e in ev:
		if e["type"] == "objective":
			for f in script_cfg.get("objective_flags", {}).get(str(e["index"]), []):
				world.flags[f] = true
	for w in _damage_watch:
		if w["structure"].damage > 0.0 or w["structure"].is_destroyed():
			world.flags[w["flag"]] = true
	world.events.append_array(ev)


func _add_structures(mission: String) -> void:
	var path := "res://data/maps/%s/objects.json" % mission
	if not FileAccess.file_exists(path):
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	for index in data["objects"].size():
		var o: Dictionary = data["objects"][index]
		var t: Dictionary = data["types"].get(str(int(o["type"])), {})
		if int(t.get("class", -1)) != 1 or float(t.get("damage_level", 0)) <= 0.0:
			continue
		var s := SimStructure.new()
		s.object_type = int(o["type"])
		s.object_index = index
		s.name = String(t.get("name", "building"))
		s.model = String(t.get("appearance", ""))
		s.damage_level = float(t["damage_level"])
		s.extent_m = float(t.get("extent_radius", 0.0)) * WORLD_UNIT_M
		s.team = int(t.get("building_team", -1))
		s.position = Vector2(float(o["x"]), float(o["y"])) * WORLD_UNIT_M
		s.facing = float(o["rotation"])
		world.add_unit(s)


func structure_near(pos_world_units: Vector2, radius_m: float = 10.0) -> SimStructure:
	var p := pos_world_units * WORLD_UNIT_M
	for u in world.units:
		if u is SimStructure and u.position.distance_to(p) <= radius_m:
			return u
	return null


## Walk speed from the model sidecar's walk gesture (m/s), when converted.
static func _apply_model_speeds(m: SimUnit) -> void:
	var path := "res://assets/mechs/%s.json" % m.model
	if not FileAccess.file_exists(path):
		return
	var side: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	for g in side.get("gestures", []):
		if g["id"] == "walk" and float(g["end_velocity"]) > 0.0:
			m.walk_speed = float(g["end_velocity"])
