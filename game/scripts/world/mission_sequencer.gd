class_name MissionSequencer
extends Node
## Runs the mission script's scripted presentation as step lists from
## data/brains/<mission>.json "sequences": waits, comms videos and voice-overs,
## each step waiting for the previous video/voice to finish (mc2_01.abl's
## tutorial stages, l.552-600 and l.700-712). Missing retail videos are skipped.

var view: Node
var videos: Dictionary = {}
var sequences: Dictionary = {}
var _queue: Array = []
var _wait_until := -1.0
var _busy := false


func setup(mission_view: Node, cfg_script: Dictionary) -> void:
	view = mission_view
	sequences = cfg_script.get("sequences", {})
	if FileAccess.file_exists("res://data/videos.json"):
		videos = JSON.parse_string(FileAccess.get_file_as_string("res://data/videos.json"))
	view.hud.comms.finished.connect(func(): _busy = false)
	start("start")


func start(name: String) -> void:
	_queue.append_array(sequences.get(name, []))


func on_objective(index: int) -> void:
	start("objective:%d" % index)


func _process(_delta: float) -> void:
	var now: float = view.world.time
	if _busy:
		if view.hud.comms.is_playing() or view.audio.voice.playing:
			return
		_busy = false
	if _wait_until >= 0.0:
		if now < _wait_until:
			return
		_wait_until = -1.0
	if view.audio.voice.playing:
		return
	while not _queue.is_empty():
		var step: Dictionary = _queue.pop_front()
		if step.has("wait"):
			_wait_until = now + float(step["wait"])
			return
		if step.has("unless_objective") and view.sm.objectives.objectives[int(step["unless_objective"])]["complete"]:
			continue
		if step.has("video"):
			if view.hud.comms.play(String(videos.get(step["video"], ""))):
				_busy = true
				return
			continue  # no retail video: skip silently
		if step.has("vo"):
			view.audio.say(String(step["vo"]))
			_busy = true
			return
