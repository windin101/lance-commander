extends Node
## Autoload "Flow": the campaign and the screens between missions.
## intro (group pre-video) -> briefing -> mission -> debrief -> next mission's briefing.
##
## Missions come in campaign.fit order (Group<g>Mission<m>). A mission is playable once
## its data is converted (data/missions/<name>.json); later ones show as "not yet
## available". Progress is saved to user://campaign.json.

const BRIEFING := "res://scenes/briefing.tscn"
const MISSION := "res://scenes/mission_view.tscn"
const DEBRIEF := "res://scenes/debrief.tscn"
const INTRO := "res://scenes/intro.tscn"

var save_path := "user://campaign.json"
var missions: Array[Dictionary] = []  # {name, group, tune, pre_video}
var current := ""  # mission being briefed / played
var completed: Dictionary = {}  # mission -> last report (won)
var last_report: Dictionary = {}


func _ready() -> void:
	load_campaign()
	load_progress()


func load_campaign(path := "res://data/campaign.json") -> void:
	missions.clear()
	if not FileAccess.file_exists(path):
		return
	var c: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var groups := int(c.get("Campaign", {}).get("GroupCount", 0))
	for g in groups:
		var grp: Dictionary = c.get("Group%d" % g, {})
		for m in int(grp.get("MissionCount", 0)):
			var mis: Dictionary = c.get("Group%dMission%d" % [g, m], {})
			if mis.has("FileName"):
				missions.append({"name": String(mis["FileName"]).to_lower(), "group": g,
					"tune": int(grp.get("Tune", -1)), "pre_video": String(grp.get("PreVideo", "")).get_basename().to_lower()})
	if current == "" and not missions.is_empty():
		current = missions[0]["name"]


static func is_available(mission: String) -> bool:
	return FileAccess.file_exists("res://data/missions/%s.json" % mission)


func index_of(mission: String) -> int:
	for i in missions.size():
		if missions[i]["name"] == mission:
			return i
	return -1


## The mission after `mission` in campaign order, or "" at the end.
func next_after(mission: String) -> String:
	var i := index_of(mission)
	return missions[i + 1]["name"] if i >= 0 and i + 1 < missions.size() else ""


func info(mission: String) -> Dictionary:
	var i := index_of(mission)
	return missions[i] if i >= 0 else {}


# --- progress ----------------------------------------------------------------------

func new_campaign() -> void:
	completed.clear()
	last_report = {}
	current = missions[0]["name"] if not missions.is_empty() else ""
	save_progress()


func record(report: Dictionary) -> void:
	last_report = report
	if report.get("won", false):
		completed[current] = report
		var nxt := next_after(current)
		if nxt != "":
			current = nxt
	save_progress()


func save_progress() -> void:
	var f := FileAccess.open(save_path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify({"current": current, "completed": completed}, " "))


func load_progress() -> void:
	if not FileAccess.file_exists(save_path):
		return
	var d = JSON.parse_string(FileAccess.get_file_as_string(save_path))
	if d is Dictionary:
		completed = d.get("completed", {})
		var c := String(d.get("current", ""))
		if index_of(c) >= 0:
			current = c


# --- screens -----------------------------------------------------------------------

func goto_briefing(mission := "") -> void:
	if mission != "":
		current = mission
	get_tree().change_scene_to_file(BRIEFING)


func launch() -> void:
	var view: Node = load(MISSION).instantiate()
	view.mission = current
	get_tree().change_scene_to_node(view)


## Called by the mission view when the player leaves a finished mission.
func mission_finished(report: Dictionary) -> void:
	record(report)
	get_tree().change_scene_to_file(DEBRIEF)
