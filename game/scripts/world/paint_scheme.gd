class_name PaintScheme
extends RefCounted
## Unit paint schemes (HD rework, 2026-10-23). A scheme is a Dictionary as in res://data/faction_paint.json
## (tools/art/faction_paint.py): base, hl1, hl2 ("#rrggbb"), regions (body region -> "base" | "hl1" | "hl2" |
## "steel"), piping / stripe / band (null, "hl1", "hl2" or a colour), decal, insignia, pattern.
## Who gets which:
##   player-owned units (the player's team in a mission, every 'Mech in the bay, lab and market): the player's
##   scheme, user://settings.cfg [paint] (default Lee's grey with red piping), as the original used the player's
##   preference colours for the campaign force (logistics.cpp:739, MechBayScreen.cpp:774);
##   House Steiner and House Liao units: their faction schemes, by the mission's colour triple;
##   everyone else: the mission's own colours on the original's team mask (mode "mask").

const PATTERNS := ["plain", "woodland", "snow", "urban", "thorin", "arkab"]  # shader order (unit_hd.gdshader)
const PLAYER_PATTERNS := ["plain", "woodland", "snow", "urban"]  # the paint panel offers these
static var settings_path := "user://settings.cfg"  # tests point this elsewhere
const REGIONS := ["body", "head", "arms", "upper_legs", "lower_legs", "feet", "weapons", "plates"]

static var _data := {}
static var _player := {}


static func data() -> Dictionary:
	if _data.is_empty():
		var p := "res://data/faction_paint.json"
		if FileAccess.file_exists(p):
			_data = JSON.parse_string(FileAccess.get_file_as_string(p))
	return _data


static func named(name: String) -> Dictionary:
	return (data().get("schemes", {}).get(name, {}) as Dictionary).duplicate(true)


## The player's scheme (a copy): the default overlaid with the saved [paint] settings.
static func player() -> Dictionary:
	if _player.is_empty():
		var s := named("player_default")
		var cfg := ConfigFile.new()
		if cfg.load(settings_path) == OK:
			for k in ["base", "hl1", "hl2", "pattern"]:
				if cfg.has_section_key("paint", k):
					s[k] = String(cfg.get_value("paint", k))
		s["owner"] = "player"
		_player = s
	return _player.duplicate(true)


## Change the player's scheme (base, hl1, hl2, pattern); saved to user://settings.cfg unless save is false.
static func set_player(base: Color, hl1: Color, hl2: Color, pattern: String, save := true) -> void:
	var s := named("player_default")
	s["base"] = "#" + base.to_html(false)
	s["hl1"] = "#" + hl1.to_html(false)
	s["hl2"] = "#" + hl2.to_html(false)
	s["pattern"] = pattern if PATTERNS.has(pattern) else "plain"
	s["owner"] = "player"
	_player = s
	if save:
		var cfg := ConfigFile.new()
		cfg.load(settings_path)
		for k in ["base", "hl1", "hl2", "pattern"]:
			cfg.set_value("paint", k, s[k])
		cfg.save(settings_path)


static func reset_cache() -> void:
	_player = {}
	_data = {}


static func _hex(v: int) -> String:
	return "#%06x" % (v & 0xFFFFFF)


## A mission colour triple [HighlightColor1, HighlightColor2, BaseColor] (as SimUnit.paint) -> its scheme: a faction
## scheme for Steiner and Liao, else the mission's colours on the team mask.
static func for_triple(paint: Array) -> Dictionary:
	if paint.size() != 3:
		return named("player_default")
	var key := "%s|%s|%s" % [_hex(int(paint[2])), _hex(int(paint[0])), _hex(int(paint[1]))]
	var t: Dictionary = data().get("triples", {}).get(key, {})
	if not t.is_empty():
		var s := named(String(t["scheme"]))
		s["faction"] = t.get("faction", "")
		return s
	return {"mode": "mask", "base": _hex(int(paint[2])), "hl1": _hex(int(paint[0])), "hl2": _hex(int(paint[1])),
		"pattern": "plain", "decal": "#d8d4c8"}


## The scheme a mission unit wears.
static func for_unit(u: SimUnit) -> Dictionary:
	if u.is_player and u.commander == 0:  # the player's own units; allies on the player's team (rebels) keep theirs
		return player()
	for a in OS.get_cmdline_user_args():  # dev: --force-scheme=<scheme> paints every other unit so (review shots)
		if a.begins_with("--force-scheme="):
			return named(a.trim_prefix("--force-scheme="))
	return for_triple(u.paint)


## The three plain colours of a scheme, as MechPaint's v1 recolour takes them: [hl1, hl2, base] Colors.
static func plain_colours(s: Dictionary) -> Array:
	return [Color(String(s.get("hl1", "#808080"))), Color(String(s.get("hl2", "#808080"))), Color(String(s.get("base", "#808080")))]
