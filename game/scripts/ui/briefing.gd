extends Control
## Mission briefing: the tactical map with numbered objective markers, the mission
## text (employer briefing and the Tactical Officer's notes), the objectives and the
## lance. Launch starts the mission; Enter does the same.

var brief: MissionBrief
var launch_button: Button
var music: AudioStreamPlayer


func _ready() -> void:
	theme = UiStyle.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiStyle.backdrop(self)
	var mission: String = Flow.current
	brief = MissionBrief.load_mission(GameData, mission)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 28)
	add_child(margin)
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 16)
	margin.add_child(page)
	page.add_child(_header(mission))
	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 18)
	page.add_child(body)
	body.add_child(_map_panel())
	body.add_child(_text_column())
	page.add_child(_footer())
	_play_tune(int(Flow.info(mission).get("tune", -1)))


func _header(mission: String) -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	var idx := Flow.index_of(mission)
	v.add_child(UiStyle.label("Mission briefing · operation %d · mission %d of %d" % [
		int(Flow.info(mission).get("group", 0)) + 1, idx + 1, Flow.missions.size()], 13, UiStyle.DIM, true))
	v.add_child(UiStyle.label(brief.title, 40, UiStyle.TEXT, true))
	if brief.summary != "":
		v.add_child(UiStyle.label(brief.summary, 17, UiStyle.DIM))
	return v


func _map_panel() -> Control:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_stretch_ratio = 1.15
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)
	v.add_child(UiStyle.heading("Tactical map"))
	var map := BriefingMap.new()
	map.brief = brief
	map.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map.custom_minimum_size = Vector2(360, 360)
	v.add_child(map)
	return panel


func _text_column() -> Control:
	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_theme_constant_override("separation", 16)
	var text_panel := PanelContainer.new()
	text_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var tv := VBoxContainer.new()
	tv.add_theme_constant_override("separation", 10)
	text_panel.add_child(tv)
	tv.add_child(UiStyle.heading("Briefing"))
	var rt := RichTextLabel.new()
	rt.bbcode_enabled = true
	rt.size_flags_vertical = Control.SIZE_EXPAND_FILL
	rt.add_theme_font_size_override("normal_font_size", 16)
	rt.add_theme_constant_override("line_separation", 3)
	rt.text = _briefing_bbcode(brief.blurb) if brief.available else \
		"[color=#%s]This mission's data is not converted yet. It arrives in a later build.[/color]" % UiStyle.WARN.to_html(false)
	tv.add_child(rt)
	col.add_child(text_panel)
	var lower := HBoxContainer.new()
	lower.add_theme_constant_override("separation", 16)
	col.add_child(lower)
	lower.add_child(_objectives_panel())
	lower.add_child(_lance_panel())
	return col


## The blurb's "Tactical Officer Notes:" section gets its own accent heading.
static func _briefing_bbcode(text: String) -> String:
	var esc := text.replace("[", "[lb]")
	var marker := "Tactical Officer Notes:"
	var at := esc.find(marker)
	if at < 0:
		return esc
	return esc.substr(0, at) + "[color=#%s][b]TACTICAL OFFICER NOTES[/b][/color]" % UiStyle.ACCENT.to_html(false) + esc.substr(at + marker.length())


func _objectives_panel() -> Control:
	var p := PanelContainer.new()
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	p.add_child(v)
	v.add_child(UiStyle.heading("Objectives"))
	var n := 0
	for o in brief.visible_objectives():
		n += 1
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		var badge := UiStyle.label(str(n), 14, UiStyle.BG)
		badge.custom_minimum_size = Vector2(22, 22)
		badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		badge.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var chip := PanelContainer.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = UiStyle.ACCENT if o["primary"] else UiStyle.WARN
		chip.add_theme_stylebox_override("panel", sb)
		chip.add_child(badge)
		row.add_child(chip)
		var l := UiStyle.label(UiStyle.objective_title(String(o["title"])) + ("" if o["primary"] else "  (secondary)"), 15)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(l)
		v.add_child(row)
	if n == 0:
		v.add_child(UiStyle.label("—", 15, UiStyle.DIM))
	return p


func _lance_panel() -> Control:
	var p := PanelContainer.new()
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	p.add_child(v)
	v.add_child(UiStyle.heading("Your lance"))
	for m in brief.lance:
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 0)
		row.add_child(UiStyle.label("%s  %s" % [m["chassis"], m["variant"]], 16))
		var who := String(m["pilot"])
		if m["callsign"] != "" and String(m["callsign"]).to_lower() != who.to_lower():
			who += " \"%s\"" % m["callsign"]
		row.add_child(UiStyle.label("%d t · %s" % [int(m["tonnage"]), who], 13, UiStyle.DIM))
		v.add_child(row)
	return p


func _footer() -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	var restart := Button.new()
	restart.text = "New campaign"
	restart.pressed.connect(func():
		Flow.new_campaign()
		Flow.goto_briefing())
	h.add_child(restart)
	if Flow.index_of(brief.mission) > 0:
		var prev := Button.new()
		prev.text = "Previous mission"
		prev.pressed.connect(func(): Flow.goto_briefing(Flow.missions[Flow.index_of(brief.mission) - 1]["name"]))
		h.add_child(prev)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(spacer)
	if not brief.available:
		h.add_child(UiStyle.label("Not yet available", 15, UiStyle.WARN))
	launch_button = Button.new()
	launch_button.text = "Launch mission"
	launch_button.add_theme_font_size_override("font_size", 20)
	launch_button.disabled = not brief.available
	launch_button.text = "To the Mech Bay" if Flow.uses_logistics(brief.mission) else "Launch mission"
	launch_button.pressed.connect(func(): Flow.proceed_from_briefing())
	h.add_child(launch_button)
	return h


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ENTER, KEY_KP_ENTER] and not launch_button.disabled:
		Flow.proceed_from_briefing()


func _play_tune(tune: int) -> void:
	if tune < 0 or not FileAccess.file_exists("res://data/audio.json"):
		return
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))
	var path := String(manifest.get("music", {}).get(str(tune), ""))
	if path == "" or not ResourceLoader.exists(path):
		return
	music = AudioStreamPlayer.new()
	music.stream = load(path)
	music.volume_db = -8.0
	add_child(music)
	music.play()
