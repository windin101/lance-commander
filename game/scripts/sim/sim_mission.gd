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
var fit: Dictionary = {}
var seed := 1
var abl: SimAbl = null  # the mission's original ABL (mission script + unit brains)
var support: SimSupport = null  # Resource Points and the player's support powers
var player_invulnerable := false  # ABL setInvulnerable (tutorials)
var use_abl := true  # false: no AI brains at all (sim tests that need passive enemies)


static func load_mission(data: Object, mission: String, seed_value: int = 1, run_abl := true) -> SimMission:
	var sm := SimMission.new()
	sm.use_abl = run_abl
	var fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % mission))
	var map := SimMap.load_mission(mission)
	map.forest_cost = float(data.gamesys["General"].get("ForestMoveCost", 50))
	var rules := SimRules.from_data(data)
	sm.world = SimWorld.new(rules, map, seed_value)
	sm.fit = fit
	sm.seed = seed_value
	sm.player_team = int(fit.get("Player0", {}).get("DefaultTeam", 0))
	var num_parts := int(fit.get("Parts", {}).get("NumParts", 0))
	# ABL part IDs come from the commander group slots, not the part number (abl-natives.md 1.3).
	var slots := {}  # part number -> [commander, group, mate]
	for key in fit:
		var km := RegEx.create_from_string("^Commander(\\d+)Group:(\\d+)$").search(key)
		if km == null:
			continue
		var mates: Array = fit[key].get("Mates", [])
		for slot in mates.size():
			if int(mates[slot]) > 0:
				slots[int(mates[slot])] = [int(km.get_string(1)), int(km.get_string(2)), slot]
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
		m.squad = int(part.get("SquadNum", 0))
		m.warrior_index = int(part.get("Pilot", i))
		m.exists = int(part.get("Exists", 1)) != 0
		m.awake = int(part.get("Active", 1)) != 0
		if slots.has(i):
			var s: Array = slots[i]
			m.group = s[1]
			m.group_index = s[2]
			m.part_id = 512 + s[0] * 192 + s[1] * 12 + s[2]
		sm.world.add_unit(m)
	sm._add_structures(mission)
	sm.objectives = SimObjectives.from_fit(fit, sm)
	sm.world.flags = sm.objectives.flags
	sm.support = SimSupport.create(sm)
	sm._attach_brains(mission)
	return sm


var script_cfg: Dictionary = {}


func _attach_brains(mission: String) -> void:
	if use_abl:
		abl = SimAbl.attach(self, mission)
	var path := "res://data/brains/%s.json" % mission
	if not FileAccess.file_exists(path):
		return
	var cfg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	script_cfg = cfg.get("script", {})  # presentation cues (voice, comms sequences, flyby)


## Advance the world one tick, evaluate objectives and the mission script;
## objective events join world.events.
func step() -> void:
	var first_new := world.events.size()
	world.step()
	support.step()
	if abl:
		abl.after_step(world.events.slice(first_new))
		objectives.script_result = abl.script_result
	var ev := objectives.update(world)
	world.events.append_array(ev)


func _add_structures(mission: String) -> void:
	var path := "res://data/maps/%s/objects.json" % mission
	if not FileAccess.file_exists(path):
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	for index in data["objects"].size():
		var o: Dictionary = data["objects"][index]
		var t: Dictionary = data["types"].get(str(int(o["type"])), {})
		if int(t.get("class", -1)) != 1 or (float(t.get("damage_level", 0)) <= 0.0 and not t.get("capturable", false)):
			continue
		var s := SimStructure.new()
		s.object_type = int(o["type"])
		s.object_index = index
		s.name = String(t.get("name", "building"))
		s.model = String(t.get("appearance", ""))
		s.damage_level = float(t["damage_level"]) if float(t["damage_level"]) > 0.0 else INF  # no DmgLevel: can't be destroyed
		s.extent_m = float(t.get("extent_radius", 0.0)) * WORLD_UNIT_M
		s.team = int(o.get("team", t.get("building_team", -1)))  # the placement's team (mc2_06's own HQ is team 0)
		s.capturable = bool(t.get("capturable", false))
		s.resource_points = int(t.get("resource_points", 0))
		s.position = Vector2(float(o["x"]), float(o["y"])) * WORLD_UNIT_M
		s.facing = float(o["rotation"])
		var cell := world.map.cell_of(s.position)
		s.part_id = 4096 + cell.y * 720 + cell.x  # abl-natives.md 1.5
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
