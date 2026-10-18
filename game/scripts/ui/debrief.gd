extends Control
## Mission debrief: result, objectives, the lance's condition and the kill tally, from
## Flow.last_report (MissionReport). Continue goes to the next mission's briefing
## (or back to this one after a loss); Replay relaunches the mission.

var report: Dictionary
var continue_button: Button


func _ready() -> void:
	theme = UiStyle.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiStyle.backdrop(self)
	report = Flow.last_report
	if report.is_empty() and OS.get_cmdline_user_args().has("--sample-report"):  # dev: screenshot without playing
		report = {"mission": "mc2_01", "title": "Scouting Patrol", "won": true, "time": 232.0,
			"objectives": [{"title": "1. Investigate Abandoned Airfield", "primary": true, "complete": true},
				{"title": "2. Destroy Hangar", "primary": true, "complete": true},
				{"title": "3. Destroy Bandit Patrol", "primary": true, "complete": true},
				{"title": "7. Destroy Bandit Supply Trucks", "primary": false, "complete": false}],
			"lance": [{"name": "Werewolf", "pilot": "Flash", "state": "Destroyed", "armour": 0},
				{"name": "Bushwacker", "pilot": "Hacksaw", "state": "Damaged", "armour": 48},
				{"name": "Bushwacker", "pilot": "Longshot", "state": "Operational", "armour": 91}],
			"kills": [{"name": "Harasser", "count": 4}, {"name": "LRM Carrier", "count": 3}, {"name": "Starslayer", "count": 1}],
			"losses": 1}
	var won: bool = report.get("won", false)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 28)
	add_child(margin)
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 16)
	margin.add_child(page)

	var head := VBoxContainer.new()
	head.add_theme_constant_override("separation", 2)
	var t := float(report.get("time", 0.0))
	head.add_child(UiStyle.label("Debrief · %s · mission time %02d:%02d" % [report.get("title", ""), int(t) / 60, int(t) % 60], 13, UiStyle.DIM, true))
	head.add_child(UiStyle.label("Mission successful" if won else "Mission failed", 40, UiStyle.ACCENT if won else UiStyle.FAIL, true))
	page.add_child(head)

	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 18)
	page.add_child(body)
	body.add_child(_objectives())
	body.add_child(_lance())
	body.add_child(_kills())
	page.add_child(_footer(won))


func _column(title: String) -> Array:
	var p := PanelContainer.new()
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	p.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	p.add_child(v)
	v.add_child(UiStyle.heading(title))
	return [p, v]


func _objectives() -> Control:
	var c := _column("Objectives")
	for o in report.get("objectives", []):
		var done: bool = o["complete"]
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		row.add_child(UiStyle.label("✔" if done else "✘", 16, UiStyle.ACCENT if done else (UiStyle.FAIL if o["primary"] else UiStyle.DIM)))
		var l := UiStyle.label(UiStyle.objective_title(String(o["title"])) + ("" if o["primary"] else "  (secondary)"), 15, UiStyle.TEXT if done else UiStyle.DIM)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(l)
		c[1].add_child(row)
	return c[0]


func _lance() -> Control:
	var c := _column("Your lance")
	for m in report.get("lance", []):
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 2)
		var state := String(m["state"])
		var col := UiStyle.ACCENT
		match state:
			"Damaged":
				col = UiStyle.WARN
			"Disabled", "Destroyed":
				col = UiStyle.FAIL
		var top := HBoxContainer.new()
		var name := UiStyle.label(String(m["name"]), 16)
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		top.add_child(name)
		top.add_child(UiStyle.label(state, 14, col, true))
		row.add_child(top)
		row.add_child(UiStyle.label("%s · armour %d%%" % [m["pilot"], int(m["armour"])], 13, UiStyle.DIM))
		var bar := ProgressBar.new()
		bar.show_percentage = false
		bar.custom_minimum_size = Vector2(0, 6)
		bar.value = float(m["armour"])
		var fill := StyleBoxFlat.new()
		fill.bg_color = col
		bar.add_theme_stylebox_override("fill", fill)
		var back := StyleBoxFlat.new()
		back.bg_color = Color(0.12, 0.15, 0.14)
		bar.add_theme_stylebox_override("background", back)
		row.add_child(bar)
		c[1].add_child(row)
	return c[0]


func _kills() -> Control:
	var c := _column("Enemy losses")
	var total := 0
	for k in report.get("kills", []):
		total += int(k["count"])
		var row := HBoxContainer.new()
		var n := UiStyle.label(String(k["name"]), 15)
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(n)
		row.add_child(UiStyle.label("× %d" % int(k["count"]), 15, UiStyle.DIM))
		c[1].add_child(row)
	c[1].add_child(UiStyle.label("Total destroyed: %d · lance losses: %d" % [total, int(report.get("losses", 0))], 14, UiStyle.DIM))
	return c[0]


func _footer(won: bool) -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	var replay := Button.new()
	replay.text = "Replay mission"
	var mission := String(report.get("mission", Flow.current))
	replay.pressed.connect(func():
		Flow.current = mission
		Flow.launch())
	h.add_child(replay)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(spacer)
	continue_button = Button.new()
	continue_button.add_theme_font_size_override("font_size", 20)
	if won:
		var nxt := Flow.current if Flow.current != mission else ""
		continue_button.text = "Next mission briefing" if nxt != "" else "Campaign complete"
		continue_button.disabled = nxt == ""
		continue_button.pressed.connect(func(): Flow.goto_briefing(nxt))
	else:
		continue_button.text = "Back to briefing"
		continue_button.pressed.connect(func(): Flow.goto_briefing(mission))
	h.add_child(continue_button)
	return h


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ENTER, KEY_KP_ENTER] and not continue_button.disabled:
		continue_button.pressed.emit()
