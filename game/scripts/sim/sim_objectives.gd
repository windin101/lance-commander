class_name SimObjectives
extends RefCounted
## Mission objectives from the mission FIT (Team0Objective*), evaluated each tick.
## Objectives activate on boolean flags and set flags when complete
## (ActionSpecies SetBooleanFlag), which chains the mission. Specific units are
## identified by their start position, as the editor stores them.
## Mission end (mission.cpp:535-650): win when every primary objective is done,
## lose when every player unit is down; either way the result lands 5 s later.

enum Result { PLAYING, WON, LOST }
const END_DELAY := 5.0
const WORLD_UNIT_M := 0.2
const SUPPORTED := ["MoveAnyUnitToArea", "MoveAllSurvivingMechsToArea", "DestroySpecificEnemyUnit",
	"DestroySpecificStructure", "DestroyAllEnemyUnits"]

var objectives: Array[Dictionary] = []
var flags: Dictionary = {}  # flag id (String) -> bool
var result: int = Result.PLAYING
var pending_result: int = Result.PLAYING
var pending_time := -1.0
var unsupported: Array[String] = []
var player_team := 0


static func from_fit(fit: Dictionary, sm: SimMission) -> SimObjectives:
	var o := SimObjectives.new()
	o.player_team = sm.player_team
	var count := int(fit.get("Team0Objectives", {}).get("NumObjectives", 0))
	for i in count:
		var block: Dictionary = fit.get("Team0Objective%d" % i, {})
		var obj := {
			"index": i,
			"title": String(block.get("Title", "Objective %d" % i)),
			"title_string": int(block.get("TitleResourceStringID", 0)) if block.get("TitleUseResourceString", false) else 0,
			"primary": int(block.get("Priority", 1)) == 1,
			"hidden": bool(block.get("HiddenTrigger", false)),
			"activate_on_flag": bool(block.get("ActivateOnFlag", false)),
			"activate_flag": String(block.get("ActivateFlagID", "")),
			"previous_primary": bool(block.get("PreviousPrimaryObjectiveMustBeComplete", false)),
			"all_previous_primary": bool(block.get("AllPreviousPrimaryObjectivesMustBeComplete", false)),
			"marker": Vector2(float(block.get("MarkerX", 0)), float(block.get("MarkerY", 0))) * WORLD_UNIT_M,
			"show_marker": bool(block.get("DisplayMarker", false)),
			"conditions": [],
			"actions": [],
			"complete": false,
			"complete_time": -1.0,
		}
		for c in int(block.get("NumConditions", 0)):
			var cb: Dictionary = fit.get("Team0Objective%dCondition%d" % [i, c], {})
			obj["conditions"].append(o._condition(cb, sm))
		for a in int(block.get("NumActions", 0)):
			var ab: Dictionary = fit.get("Team0Objective%dAction%d" % [i, a], {})
			obj["actions"].append({"kind": String(ab.get("ActionSpeciesString", "")),
				"flag": String(ab.get("FlagID", "")), "value": bool(ab.get("Value", true))})
		o.objectives.append(obj)
	return o


func _condition(cb: Dictionary, sm: SimMission) -> Dictionary:
	var kind := String(cb.get("ConditionSpeciesString", ""))
	var c := {"kind": kind}
	match kind:
		"MoveAnyUnitToArea", "MoveAllSurvivingMechsToArea":
			c["center"] = Vector2(float(cb["TargetCenterX"]), float(cb["TargetCenterY"])) * WORLD_UNIT_M
			c["radius"] = float(cb["TargetRadius"]) * WORLD_UNIT_M
		"DestroySpecificEnemyUnit":
			c["unit"] = _unit_at(sm.world, Vector2(float(cb["PositionX"]), float(cb["PositionY"])) * WORLD_UNIT_M)
		"DestroySpecificStructure":
			c["unit"] = sm.structure_near(Vector2(float(cb["PositionX"]), float(cb["PositionY"])))
		"DestroyAllEnemyUnits":
			pass
		_:
			if not unsupported.has(kind):
				unsupported.append(kind)
	return c


static func _unit_at(world: SimWorld, pos: Vector2) -> SimUnit:
	var best: SimUnit = null
	var best_d := 3.0
	for u in world.units:
		if u.is_mover() and u.position.distance_to(pos) < best_d:
			best_d = u.position.distance_to(pos)
			best = u
	return best


func is_active(obj: Dictionary) -> bool:
	if obj["complete"]:
		return false
	if obj["activate_on_flag"] and not flags.get(obj["activate_flag"], false):
		return false
	if obj["all_previous_primary"] or obj["previous_primary"]:
		for prev in objectives:
			if prev["index"] >= obj["index"]:
				break
			if prev["primary"] and not prev["hidden"] and not prev["complete"]:
				if obj["all_previous_primary"] or prev["index"] == obj["index"] - 1:
					return false
	return true


## Evaluate active objectives; returns events ({"type": "objective", ...}).
func update(world: SimWorld) -> Array[Dictionary]:
	var events: Array[Dictionary] = []
	for obj in objectives:
		if not is_active(obj):
			continue
		var all_met: bool = not obj["conditions"].is_empty()
		for c in obj["conditions"]:
			if not _met(c, world):
				all_met = false
				break
		if all_met:
			obj["complete"] = true
			obj["complete_time"] = world.time
			for a in obj["actions"]:
				if a["kind"] == "SetBooleanFlag":
					flags[a["flag"]] = a["value"]
			events.append({"type": "objective", "index": obj["index"], "title": obj["title"], "hidden": obj["hidden"]})
	_check_end(world, events)
	return events


func _met(c: Dictionary, world: SimWorld) -> bool:
	match c["kind"]:
		"MoveAnyUnitToArea":
			for u in world.units:
				if u.team == player_team and u.is_mover() and not u.is_disabled() \
						and u.position.distance_to(c["center"]) <= c["radius"]:
					return true
			return false
		"MoveAllSurvivingMechsToArea":
			var any := false
			for u in world.units:
				if u.team == player_team and u is SimMech and not u.is_disabled():
					any = true
					if u.position.distance_to(c["center"]) > c["radius"]:
						return false
			return any
		"DestroySpecificEnemyUnit", "DestroySpecificStructure":
			return c.get("unit") == null or c["unit"].is_disabled()
		"DestroyAllEnemyUnits":
			for u in world.units:
				if u.team != player_team and u.is_mover() and not u.is_disabled():
					return false
			return true
	return false


func _check_end(world: SimWorld, events: Array[Dictionary]) -> void:
	if result != Result.PLAYING:
		return
	if pending_result == Result.PLAYING:
		var player_alive := false
		for u in world.units:
			if u.team == player_team and u.is_mover() and not u.is_disabled():
				player_alive = true
				break
		if not player_alive:
			pending_result = Result.LOST
		else:
			var all_primary := true
			for obj in objectives:
				if obj["primary"] and not obj["hidden"] and not obj["complete"]:
					all_primary = false
					break
			if all_primary and not objectives.is_empty():
				pending_result = Result.WON
		if pending_result != Result.PLAYING:
			pending_time = world.time + END_DELAY
	elif world.time >= pending_time:
		result = pending_result
		events.append({"type": "mission_end", "won": result == Result.WON})


func visible_objectives() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for obj in objectives:
		if obj["hidden"]:
			continue
		if obj["complete"] or is_active(obj):
			out.append(obj)
	return out
