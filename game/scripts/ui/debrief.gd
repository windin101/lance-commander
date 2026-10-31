extends Control
## Mission debrief (style guide 5.9, amber layer): the result banner, payout, objectives, the
## lance's condition and the kill tally, from Flow.last_report (MissionReport). Continue goes to the next mission's briefing
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
			"kills": [{"name": "Harasser", "force": "Pirates", "count": 4}, {"name": "LRM Carrier", "force": "Pirates", "count": 3},
				{"name": "Starslayer", "count": 1}],
			"losses": 1, "payout": 85000}
	var won: bool = report.get("won", false)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, int(StyleTokens.geo("outer_margin")))
	add_child(margin)
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", int(StyleTokens.geo("gutter")) * 2)
	margin.add_child(page)
	page.add_child(_header(won))

	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", int(StyleTokens.geo("gutter")))
	page.add_child(body)
	var cols := [_objectives(), _lance(), _kills()]
	for c in cols:
		body.add_child(c)
	page.add_child(_footer(won))
	if is_inside_tree():
		StyleTokens.boot_flicker(self)
		for i in cols.size():
			StyleTokens.panel_in.call_deferred(cols[i], 0.12 + i * StyleTokens.motion_s("hud_stagger"))


## The result banner (5.9): VICTORY / PYRRHIC / DEFEAT in Chakra Petch 56 caps, ok / warn / crit, with an
## underline sweeping out under it; beside it the payout total in amber.
func _result() -> Array:
	var won: bool = report.get("won", false)
	var lance: Array = report.get("lance", [])
	if not won:
		return ["Defeat", UiStyle.CRIT]
	if not lance.is_empty() and int(report.get("losses", 0)) * 2 >= lance.size():
		return ["Pyrrhic victory", UiStyle.WARN]  # won with half the lance or more disabled
	return ["Victory", UiStyle.STATE_OK]


func _header(won: bool) -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", int(StyleTokens.geo("gutter")) * 2)
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 6)
	h.add_child(left)
	var t := float(report.get("time", 0.0))
	left.add_child(StyleTokens.label("Debrief · %s · mission time %02d:%02d" % [UiStyle.clean(String(report.get("title", ""))),
		int(t) / 60, int(t) % 60], "CapsLabel"))
	var r := _result()
	var banner := StyleTokens.label(r[0], "BannerLabel", r[1])
	banner.name = "Banner"
	left.add_child(banner)
	var sweep := ColorRect.new()
	sweep.name = "Sweep"
	sweep.color = r[1]
	sweep.custom_minimum_size = Vector2(0, StyleTokens.geo("line_active"))
	sweep.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	left.add_child(sweep)
	_sweep.call_deferred(sweep, banner)
	# payout (amber, mono, counting up)
	var pay := VBoxContainer.new()
	pay.size_flags_vertical = Control.SIZE_SHRINK_END
	pay.add_theme_constant_override("separation", 2)
	var pl := StyleTokens.label("Contract payout", "CapsLabel")
	pl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	pay.add_child(pl)
	var amount := Label.new()
	amount.name = "Payout"
	amount.theme_type_variation = "MonoLabel"
	amount.add_theme_font_size_override("font_size", StyleTokens.size("title"))
	amount.add_theme_color_override("font_color", UiStyle.AMBER_500 if won else UiStyle.STEEL_300)
	amount.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	pay.add_child(amount)
	var cb := int(report.get("payout", 0)) if won else 0
	amount.text = "%s C-B" % BayKit.money(cb)
	amount.ready.connect(func(): _count_money(amount, cb))
	h.add_child(pay)
	return h


func _sweep(sweep: ColorRect, banner: Label) -> void:
	var full := banner.get_minimum_size().x
	if StyleTokens.reduce_motion() or not is_inside_tree():
		sweep.custom_minimum_size.x = full
		return
	create_tween().tween_property(sweep, "custom_minimum_size:x", full, StyleTokens.motion_s("count_up")) \
		.set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)


func _count_money(l: Label, value: int) -> void:
	if StyleTokens.reduce_motion():
		return
	var tw := create_tween()
	tw.tween_method(func(v: float): l.text = "%s C-B" % BayKit.money(roundi(v)), 0.0, float(value),
		StyleTokens.motion_s("count_up")).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)


func _column(title: String) -> Array:
	var p := PanelContainer.new()
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	p.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", int(StyleTokens.geo("grid")) + 2)
	p.add_child(v)
	v.add_child(UiStyle.heading(title))
	return [p, v]


func _objectives() -> Control:
	var c := _column("Objectives")
	for o in report.get("objectives", []):
		var done: bool = o["complete"]
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 10)
		var mark := UiStyle.label("✔" if done else "✘", StyleTokens.size("body"), UiStyle.STATE_OK if done else (UiStyle.CRIT if o["primary"] else UiStyle.STEEL_500))
		mark.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		row.add_child(mark)
		var l := UiStyle.label(UiStyle.objective_title(String(o["title"])), StyleTokens.size("body"), UiStyle.TEXT if done else UiStyle.DIM)
		if o["primary"] and done:
			l.add_theme_font_override("font", StyleTokens.font("body", 0, true))
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(l)
		if not o["primary"]:
			row.add_child(StyleTokens.label("Secondary", "CapsLabel"))
		c[1].add_child(row)
	return c[0]


func _lance() -> Control:
	var c := _column("Your lance")
	for m in report.get("lance", []):
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		var state := String(m["state"])
		var col := UiStyle.STATE_OK
		match state:
			"Damaged":
				col = UiStyle.WARN
			"Disabled", "Destroyed":
				col = UiStyle.CRIT
		var top := HBoxContainer.new()
		var name := UiStyle.label(String(m["name"]), StyleTokens.size("body"), UiStyle.WHITE)
		name.add_theme_font_override("font", StyleTokens.font("body", 0, true))
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		top.add_child(name)
		var st := StyleTokens.label(state, "CapsLabel", col)
		top.add_child(st)
		row.add_child(top)
		var sub := HBoxContainer.new()
		var who := UiStyle.label(String(m["pilot"]), StyleTokens.size("label") + 1, UiStyle.DIM)
		who.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		sub.add_child(who)
		var arm := StyleTokens.label("ARM %3d%%" % int(m["armour"]), "MicroLabel")
		sub.add_child(arm)
		row.add_child(sub)
		row.add_child(_bar(float(m["armour"]), col))
		c[1].add_child(row)
	return c[0]


## A 6 px segmented bar (4.3): ink-600 track, state-coloured fill, a tick every 10 %.
func _bar(value: float, col: Color) -> Control:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.custom_minimum_size = Vector2(0, StyleTokens.geo("slider_track"))
	bar.value = value
	var fill := StyleBoxFlat.new()
	fill.bg_color = col
	bar.add_theme_stylebox_override("fill", fill)
	bar.draw.connect(func():
		var n := int(StyleTokens.geo("slider_segments"))
		for i in range(1, n):
			var x := bar.size.x * i / n
			bar.draw_line(Vector2(x, 0), Vector2(x, bar.size.y), UiStyle.INK_800, 1.0))
	return bar


func _kills() -> Control:
	var c := _column("Enemy losses")
	var total := 0
	for k in report.get("kills", []):
		total += int(k["count"])
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 10)
		var n := UiStyle.label(String(k["name"]), StyleTokens.size("body"))
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(n)
		if String(k.get("force", "")) != "":
			row.add_child(StyleTokens.label(String(k["force"]), "CapsLabel"))
		var cnt := StyleTokens.label("× %d" % int(k["count"]), "MonoLabel")
		cnt.custom_minimum_size.x = 44
		cnt.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		row.add_child(cnt)
		c[1].add_child(row)
	var sep := HSeparator.new()
	c[1].add_child(sep)
	var tot := HBoxContainer.new()
	var tl := StyleTokens.label("Destroyed", "CapsLabel")
	tl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tot.add_child(tl)
	tot.add_child(StyleTokens.label("%d" % total, "MonoLabel"))
	c[1].add_child(tot)
	var loss := HBoxContainer.new()
	var ll := StyleTokens.label("Lance losses", "CapsLabel")
	ll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	loss.add_child(ll)
	var lost := int(report.get("losses", 0))
	loss.add_child(StyleTokens.label("%d" % lost, "MonoLabel", UiStyle.CRIT if lost > 0 else Color(0, 0, 0, 0)))
	c[1].add_child(loss)
	return c[0]


func _footer(won: bool) -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", int(StyleTokens.geo("gutter")))
	var replay := Button.new()
	replay.theme_type_variation = "SecondaryButton"
	replay.text = "REPLAY MISSION"
	var mission := String(report.get("mission", Flow.current))
	replay.pressed.connect(func():
		Flow.current = mission
		Flow.launch())
	h.add_child(replay)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(spacer)
	continue_button = Button.new()
	continue_button.custom_minimum_size = Vector2(280, StyleTokens.geo("button_min_height"))
	if won:
		var nxt := Flow.current if Flow.current != mission else ""
		continue_button.text = "NEXT MISSION BRIEFING" if nxt != "" else "CAMPAIGN COMPLETE"
		continue_button.disabled = nxt == ""
		continue_button.pressed.connect(func(): Flow.after_debrief(nxt))
	else:
		continue_button.text = "BACK TO BRIEFING"
		continue_button.pressed.connect(func(): Flow.goto_briefing(mission))
	h.add_child(continue_button)
	return h


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ENTER, KEY_KP_ENTER] and not continue_button.disabled:
		continue_button.pressed.emit()
