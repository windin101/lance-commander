class_name SimObjectives
extends RefCounted
## Team 0 mission objectives from the mission FIT, evaluated as the original does
## (docs/specs/capture-and-objectives.md, part B):
## - each condition reports undetermined / success / fail; success conditions are
##   ANDed (zero conditions = success), failure conditions are ANDed and override
##   success; a resolved objective latches and runs its actions once;
## - objectives activate on a flag; "all previous primaries" gates evaluation;
## - the mission is won when every active primary has succeeded and no
##   flag-activated primary is still waiting, lost on a failed primary, when every
##   player unit is down, or when the mission's time limit passes; then a 5 s delay.
## Targets are matched by their FIT position; a condition whose target can't be found
## is dropped, as in the original (B2).

enum Result { PLAYING, WON, LOST }
enum Status { UNDETERMINED, SUCCESS, FAILED }
const END_DELAY := 5.0
const WORLD_UNIT_M := 0.2
const EXTRACT_CLEAR_M := 256.0  # MaxUnitExtractDistance: no other commander's mover this close
const MATCH_M := 1.0  # targets sit exactly at their FIT position
const SUPPORTED := ["MoveAnyUnitToArea", "MoveAllSurvivingMechsToArea", "DestroySpecificEnemyUnit",
	"DestroySpecificStructure", "DestroyAllEnemyUnits", "DestroyNumberOfEnemyUnits", "CaptureSpecificUnit",
	"CaptureSpecificStructure", "CaptureOrDestroySpecificEnemyUnit", "CaptureOrDestroySpecificStructure",
	"BooleanFlagIsSet", "ElapsedMissionTime"]

var objectives: Array[Dictionary] = []
var flags: Dictionary = {}  # flag id (String) -> bool
var result: int = Result.PLAYING
var pending_result: int = Result.PLAYING
var pending_time := -1.0
var unsupported: Array[String] = []
var dropped := 0
var bonus_files: Array[String] = []  # conditions whose target could not be found (silently dropped, B1)
var player_team := 0
var time_limit := -1.0  # MissionSettings TimeLimit, seconds
var script_result := 0  # the mission script's return value (scenario result: 1-2 lost, 4-5 won)


static func from_fit(fit: Dictionary, sm: SimMission) -> SimObjectives:
	var o := SimObjectives.new()
	o.player_team = sm.player_team
	o.time_limit = float(fit.get("MissionSettings", {}).get("TimeLimit", -1.0))
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
			"resource_points": int(block.get("ResourcePoints", 0)),
			"conditions": [],
			"failure_conditions": [],
			"actions": [],
			"failure_actions": [],
			"active": not bool(block.get("ActivateOnFlag", false)),
			"status": Status.UNDETERMINED,
			"complete": false,
			"failed": false,
			"complete_time": -1.0,
		}
		for c in int(block.get("NumConditions", 0)):
			var cond = o._condition(fit.get("Team0Objective%dCondition%d" % [i, c], {}), "ConditionSpeciesString", sm)
			if cond != null:
				obj["conditions"].append(cond)
		for c in int(block.get("NumFailureConditions", 0)):
			var cond = o._condition(fit.get("Team0Objective%dFailureCondition%d" % [i, c], {}), "FailureConditionSpeciesString", sm)
			if cond != null:
				obj["failure_conditions"].append(cond)
		for a in int(block.get("NumActions", 0)):
			obj["actions"].append(_action(fit.get("Team0Objective%dAction%d" % [i, a], {}), "ActionSpeciesString"))
		for a in int(block.get("NumFailureActions", 0)):
			obj["failure_actions"].append(_action(fit.get("Team0Objective%dFailureAction%d" % [i, a], {}), "FailureActionSpeciesString"))
		o.objectives.append(obj)
	return o


static func _action(ab: Dictionary, key: String) -> Dictionary:
	return {"kind": String(ab.get(key, ab.get("ActionSpeciesString", ""))), "flag": String(ab.get("FlagID", "")),
		"value": bool(ab.get("Value", true)), "wav": String(ab.get("WAVFileName", "")),
		"file": String(ab.get("PurchaseFileName", "")).replace("\\", "/").get_file().get_basename().to_lower()}


## A parsed condition, or null when its target can't be resolved (dropped, B1/B2).
func _condition(cb: Dictionary, key: String, sm: SimMission) -> Variant:
	var kind := String(cb.get(key, cb.get("ConditionSpeciesString", "")))
	var c := {"kind": kind}
	var pos := Vector2(float(cb.get("PositionX", 0.0)), float(cb.get("PositionY", 0.0))) * WORLD_UNIT_M
	match kind:
		"MoveAnyUnitToArea", "MoveAllSurvivingMechsToArea":
			c["center"] = Vector2(float(cb["TargetCenterX"]), float(cb["TargetCenterY"])) * WORLD_UNIT_M
			c["radius"] = float(cb["TargetRadius"]) * WORLD_UNIT_M
		"DestroySpecificEnemyUnit", "CaptureSpecificUnit", "CaptureOrDestroySpecificEnemyUnit":
			c["unit"] = _unit_at(sm.world, pos, player_team)
		"DestroySpecificStructure", "CaptureSpecificStructure", "CaptureOrDestroySpecificStructure":
			c["unit"] = sm.structure_near(pos / WORLD_UNIT_M)
		"DestroyAllEnemyUnits":
			pass
		"DestroyNumberOfEnemyUnits":
			c["num"] = int(cb.get("Num", 0))
		"BooleanFlagIsSet":
			c["flag"] = String(cb.get("FlagID", str(cb.get("FlagIndex", ""))))
			c["value"] = bool(cb.get("Value", true))
		"ElapsedMissionTime":
			c["time"] = float(cb.get("Time", 0.0))
		_:
			if not unsupported.has(kind):
				unsupported.append(kind)
			return c
	if c.has("unit"):
		if c["unit"] == null:
			dropped += 1
			return null
		if kind.begins_with("Capture"):
			c["unit"].capturable = true  # naming a target makes it capturable (A1)
	return c


## The first mover at a spawn position whose team isn't the objective's team (B2).
static func _unit_at(world: SimWorld, pos: Vector2, team: int) -> SimUnit:
	var best: SimUnit = null
	var best_d := MATCH_M
	for u in world.units:
		if u.is_mover() and u.team != team and u.position.distance_to(pos) < best_d:
			best_d = u.position.distance_to(pos)
			best = u
	return best


# --- evaluation ------------------------------------------------------------------------

static func dead(u: SimUnit) -> bool:
	return u.is_disabled() or u.ejected


func captured(u: SimUnit) -> bool:
	return not u.is_destroyed() and u.team == player_team


func _cond_status(c: Dictionary, world: SimWorld) -> int:
	var u: SimUnit = c.get("unit")
	match c["kind"]:
		"DestroySpecificEnemyUnit", "CaptureOrDestroySpecificEnemyUnit":
			return Status.SUCCESS if dead(u) or captured(u) else Status.UNDETERMINED
		"DestroySpecificStructure":
			return Status.SUCCESS if u.is_destroyed() else Status.UNDETERMINED
		"CaptureSpecificUnit", "CaptureSpecificStructure":
			if u.team == player_team and not u.is_destroyed():
				return Status.SUCCESS
			return Status.FAILED if u.is_destroyed() or not u.exists else Status.UNDETERMINED
		"CaptureOrDestroySpecificStructure":
			return Status.SUCCESS if u.is_destroyed() or u.team == player_team else Status.UNDETERMINED
		"DestroyAllEnemyUnits":
			for m in world.units:
				if m.is_mover() and m.team != player_team and not dead(m):
					return Status.UNDETERMINED
			return Status.SUCCESS
		"DestroyNumberOfEnemyUnits":
			var n := 0
			for m in world.units:
				if m.is_mover() and m.team != player_team and dead(m):
					n += 1
			return Status.SUCCESS if n >= int(c["num"]) else Status.UNDETERMINED
		"MoveAnyUnitToArea":
			for m in world.units:
				if _player_force(m) and not dead(m) and m.position.distance_to(c["center"]) < c["radius"]:
					return Status.SUCCESS
			return Status.UNDETERMINED
		"MoveAllSurvivingMechsToArea":
			for m in world.units:
				if _player_force(m) and m is SimMech and not dead(m) and m.position.distance_to(c["center"]) > c["radius"]:
					return Status.UNDETERMINED
			for m in world.units:
				if m.is_mover() and m.exists and m.commander != 0 and not dead(m) and not m.hulk \
						and m.position.distance_to(c["center"]) <= EXTRACT_CLEAR_M:
					return Status.UNDETERMINED  # any other commander's unit, allies included (quirk)
			return Status.SUCCESS
		"BooleanFlagIsSet":
			return Status.SUCCESS if flags.get(c["flag"], false) == c["value"] else Status.UNDETERMINED
		"ElapsedMissionTime":
			return Status.SUCCESS if world.time >= float(c["time"]) else Status.UNDETERMINED
	return Status.UNDETERMINED


## The player's own units: the player's commander, on the GUI (no allies, no hulks).
func _player_force(m: SimUnit) -> bool:
	return m.is_mover() and m.exists and m.team == player_team and m.commander == 0 and not m.hulk


func _evaluate(obj: Dictionary, world: SimWorld) -> int:
	var status: int = Status.SUCCESS
	for c in obj["conditions"]:
		var s := _cond_status(c, world)
		if s == Status.FAILED:
			return Status.FAILED
		if s == Status.UNDETERMINED:
			status = Status.UNDETERMINED
	if not obj["failure_conditions"].is_empty():
		var all_met := true
		for c in obj["failure_conditions"]:
			if _cond_status(c, world) != Status.SUCCESS:
				all_met = false
				break
		if all_met:
			return Status.FAILED
	return status


func _gated(obj: Dictionary) -> bool:
	if not (obj["all_previous_primary"] or obj["previous_primary"]):
		return false
	for prev in objectives:
		if prev["index"] >= obj["index"]:
			break
		if prev["primary"] and prev["active"] and prev["status"] != Status.SUCCESS:
			if obj["all_previous_primary"] or prev["index"] == obj["index"] - 1:
				return true
	return false


## Active, unresolved and not gated: what the HUD lists as current.
func is_active(obj: Dictionary) -> bool:
	return obj["active"] and obj["status"] == Status.UNDETERMINED and not _gated(obj)


## One sweep (B5); returns events ({"type": "objective" / "objective_failed" / "abl_wave" / "mission_end"}).
func update(world: SimWorld) -> Array[Dictionary]:
	var events: Array[Dictionary] = []
	var mission_status: int = Status.SUCCESS
	var any_primary := false
	for obj in objectives:
		var counts: bool = obj["primary"] and not obj["hidden"]  # hidden triggers don't decide the mission (B6)
		if counts:
			any_primary = true
		if not obj["active"]:
			if obj["activate_on_flag"]:
				if counts:
					mission_status = Status.UNDETERMINED
				if flags.get(obj["activate_flag"], false):
					obj["active"] = true  # evaluated from the next sweep
			continue
		if obj["status"] == Status.UNDETERMINED and not _gated(obj):
			var s := _evaluate(obj, world)
			if s != Status.UNDETERMINED:
				_resolve(obj, s, world, events)
		if counts:
			if obj["status"] == Status.FAILED:
				mission_status = Status.FAILED
				break
			if obj["status"] == Status.UNDETERMINED:
				mission_status = Status.UNDETERMINED
	_check_end(world, events, mission_status if any_primary else Status.UNDETERMINED)
	return events


func _resolve(obj: Dictionary, status: int, world: SimWorld, events: Array[Dictionary]) -> void:
	obj["status"] = status
	obj["complete"] = status == Status.SUCCESS
	obj["failed"] = status == Status.FAILED
	obj["complete_time"] = world.time
	var actions: Array = obj["actions"] if status == Status.SUCCESS else obj["failure_actions"]
	for a in actions:
		match a["kind"]:
			"SetBooleanFlag":
				flags[a["flag"]] = a["value"]
			"PlayWAV":
				events.append({"type": "abl_wave", "file": a["wav"]})
			"MakeNewTechnologyAvailable":
				bonus_files.append(a["file"])  # the campaign picks it up (campaign-layer.md 5.3)
	events.append({"type": "objective" if status == Status.SUCCESS else "objective_failed",
		"index": obj["index"], "title": obj["title"], "hidden": obj["hidden"]})


func _check_end(world: SimWorld, events: Array[Dictionary], mission_status: int) -> void:
	if result != Result.PLAYING:
		return
	if pending_result == Result.PLAYING:
		var player_alive := false
		for u in world.units:
			if _player_force(u) and not dead(u):
				player_alive = true
				break
		if script_result in [1, 2, 3]:
			pending_result = Result.LOST
		elif script_result in [4, 5]:
			pending_result = Result.WON
		elif not player_alive:
			pending_result = Result.LOST  # all-dead is always a loss
		elif mission_status == Status.FAILED:
			pending_result = Result.LOST
		elif mission_status == Status.SUCCESS:
			pending_result = Result.WON
		elif time_limit > 0.0 and world.time >= time_limit:
			pending_result = Result.LOST
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
		if obj["status"] != Status.UNDETERMINED or is_active(obj):
			out.append(obj)
	return out
