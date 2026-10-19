extends Control
## Salvage (campaign-layer.md 6.2): after a win, every disabled (not destroyed) 'Mech of
## any team, your own included, can be bought back at 80% of its price. Bought 'Mechs
## join the reserve without a pilot.

var camp: Campaign
var _list: VBoxContainer
var _status: Label
var _taken := {}  # candidate index -> true


func _ready() -> void:
	theme = UiStyle.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiStyle.backdrop(self)
	camp = Flow.campaign
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 28)
	add_child(margin)
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 14)
	margin.add_child(page)
	page.add_child(UiStyle.label("Salvage · %s" % Flow.last_report.get("title", ""), 13, UiStyle.DIM, true))
	_status = UiStyle.label("", 26, UiStyle.TEXT, true)
	page.add_child(_status)
	var panel := PanelContainer.new()
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var outer := VBoxContainer.new()
	panel.add_child(outer)
	outer.add_child(UiStyle.heading("Disabled 'Mechs on the field · 80% of their price"))
	_list = VBoxContainer.new()
	_list.add_theme_constant_override("separation", 8)
	outer.add_child(_list)
	page.add_child(panel)
	var foot := HBoxContainer.new()
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foot.add_child(spacer)
	var done := Button.new()
	done.text = "Done"
	done.add_theme_font_size_override("font_size", 20)
	done.pressed.connect(func():
		Flow.save_progress()
		Flow.goto_briefing())
	foot.add_child(done)
	page.add_child(foot)
	_refresh()


func _candidates() -> Array:
	var c: Array = Flow.last_report.get("salvage", []).duplicate()
	c.sort_custom(func(a, b): return camp.salvage_price(a["chassis"], int(a["variant"])) < camp.salvage_price(b["chassis"], int(b["variant"])))
	return c


func _refresh() -> void:
	for ch in _list.get_children():
		ch.queue_free()
	_status.text = "C-Bills %s" % _money(camp.c_bills)
	var cands := _candidates()
	for i in cands.size():
		var c: Dictionary = cands[i]
		var cost := camp.salvage_price(c["chassis"], int(c["variant"]))
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 10)
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		info.add_child(UiStyle.label(String(c["name"]), 16, UiStyle.ACCENT if _taken.has(i) else UiStyle.TEXT))
		info.add_child(UiStyle.label("%d t · %s C-Bills" % [int(camp.tonnage(c["chassis"])), _money(cost)], 13, UiStyle.DIM))
		row.add_child(info)
		var b := Button.new()
		b.toggle_mode = true
		b.button_pressed = _taken.has(i)
		b.text = "Taken" if _taken.has(i) else "Take"
		b.disabled = not _taken.has(i) and cost > camp.c_bills
		b.toggled.connect(func(on):
			if on:
				camp.c_bills -= cost
				_taken[i] = c
			else:
				camp.c_bills += cost
				_taken.erase(i)
			_refresh())
		row.add_child(b)
		_list.add_child(row)
	if cands.is_empty():
		_list.add_child(UiStyle.label("Nothing to salvage.", 15, UiStyle.DIM))


func _exit_tree() -> void:
	for i in _taken:
		var c: Dictionary = _taken[i]
		camp.add_mech(String(c["chassis"]), int(c["variant"]))  # paid when ticked
	_taken.clear()
	Flow.save_progress()


static func _money(v: int) -> String:
	var s := str(absi(v))
	var out := ""
	while s.length() > 3:
		out = "," + s.right(3) + out
		s = s.left(s.length() - 3)
	return ("-" if v < 0 else "") + s + out
