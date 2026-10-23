class_name Subtitles
extends RefCounted
## Comms subtitles (an option, on by default): the speaker and text of each voice line, from
## res://data/subtitles.json (tools/convert/subtitles.py: local Whisper transcripts of the
## original's own audio, reviewed). The original showed none.
##   vo      mission voice-overs by sound name (as audio.json keys them, e.g. "mc2_12_1"), with
##           timed segments so a long line follows the audio
##   pilots  radio lines by "pilot<n>/<wav name>"; a profile's pilotAudio "pilot<letter>" is
##           voice n = the letter's place in the alphabet (radio.cpp:78, pilot<letter>.pak)
## The setting is user://settings.cfg [comms] subtitles, beside the HUD scale.

static var settings_path := UiStyle.SETTINGS_PATH  # tests point this elsewhere
static var data_path := "res://data/subtitles.json"
static var _data := {}
static var _on := -1  # -1 unread, 0 off, 1 on


static func data() -> Dictionary:
	if _data.is_empty():
		var d = JSON.parse_string(FileAccess.get_file_as_string(data_path)) if FileAccess.file_exists(data_path) else null
		_data = d if d is Dictionary else {"vo": {}, "pilots": {}}
	return _data


static func reset_cache() -> void:
	_data = {}
	_on = -1


static func enabled() -> bool:
	if _on < 0:
		var cfg := ConfigFile.new()
		_on = 1 if cfg.load(settings_path) != OK or bool(cfg.get_value("comms", "subtitles", true)) else 0
	return _on == 1


static func set_enabled(v: bool, save := true) -> void:
	_on = 1 if v else 0
	if save:
		var cfg := ConfigFile.new()
		cfg.load(settings_path)
		cfg.set_value("comms", "subtitles", v)
		cfg.save(settings_path)


## A voice-over's entry {speaker, text, duration, segments}, or {}.
static func vo(name: String) -> Dictionary:
	return data().get("vo", {}).get(name.to_lower(), {})


## [speaker, text] to show at t seconds into voice-over name: the segment playing then (the
## last one started, so a gap keeps the previous line up), else the whole text.
static func vo_line(name: String, t: float) -> Array:
	var e := vo(name)
	if e.is_empty():
		return ["", ""]
	var text := String(e.get("text", ""))
	var who := String(e.get("speaker", ""))
	var segs: Array = e.get("segments", [])
	if not segs.is_empty():
		var cur: Array = segs[0]
		for s in segs:
			if t >= float(s[0]):
				cur = s
		text = String(cur[2])
		if cur.size() > 3:  # a line with two voices names each segment's speaker
			who = String(cur[3])
	return [who, text]


## The voice number (1-26) a pilot profile speaks with, or 0.
static func voice_of(profile: String, pilots: Dictionary) -> int:
	var a := String(pilots.get(profile, {}).get("General", {}).get("pilotAudio", "")).to_lower()
	if a.length() == 6 and a.begins_with("pilot"):
		var n := a.unicode_at(5) - 96
		return n if n >= 1 and n <= 26 else 0
	return 0


## A pilot's radio line {speaker, voice, text, duration} for a message stem ("acknowledgea",
## "underattackb"...), or {}.
static func pilot_line(profile: String, stem: String, pilots: Dictionary) -> Dictionary:
	var n := voice_of(profile, pilots)
	if n == 0:
		return {}
	return data().get("pilots", {}).get("pilot%d/plt%d_%s" % [n, n, stem.to_lower()], {})
