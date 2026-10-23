class_name PauseMenu
extends CanvasLayer
## In-mission overlay. Esc pauses: Resume / Restart mission / Abort to briefing.
## When the mission ends the same panel offers Continue (to the debrief) and Replay;
## Enter continues. Framed in the HUD style, with the HUD scale setting (0.6-1.0, saved
## to user://settings.cfg; the HUD rebuilds at the new size) and comms subtitles on/off.

var view: Node  # MissionView
var panel: PanelContainer
var title: Label
var buttons: VBoxContainer
var ended := false
var scale_row: HBoxContainer
var scale_slider: HSlider
var scale_value: Label
var subtitles_button: Button  # comms subtitles on/off (Subtitles, user://settings.cfg [comms])


func _ready() -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	var u := UiStyle.hud_unit(1080.0, 1.0) * 0.85
	root.theme = UiStyle.hud_theme(u)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(340, 0)
	panel.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(u, Vector4(u * 1.6, u * 1.2, u * 1.6, u * 1.4)))
	center.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	panel.add_child(v)
	title = UiStyle.label("Paused", 26, UiStyle.HUD_INK, true)
	title.add_theme_font_override("font", UiStyle.font("display700", 3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(title)
	buttons = VBoxContainer.new()
	buttons.add_theme_constant_override("separation", 8)
	v.add_child(buttons)
	scale_row = HBoxContainer.new()
	scale_row.add_theme_constant_override("separation", 10)
	v.add_child(scale_row)
	var sl := UiStyle.label("HUD scale", 15, UiStyle.HUD_DIM, true)
	sl.add_theme_font_override("font", UiStyle.font("display600", 2))
	scale_row.add_child(sl)
	scale_slider = HSlider.new()
	scale_slider.min_value = UiStyle.HUD_SCALE_MIN
	scale_slider.max_value = UiStyle.HUD_SCALE_MAX
	scale_slider.step = 0.05
	scale_slider.value = UiStyle.hud_scale()
	scale_slider.focus_mode = Control.FOCUS_NONE
	scale_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scale_slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	scale_row.add_child(scale_slider)
	scale_value = UiStyle.label("", 15, UiStyle.HUD_INK)
	scale_value.add_theme_font_override("font", UiStyle.font("mono"))
	scale_value.custom_minimum_size.x = 44
	scale_row.add_child(scale_value)
	scale_slider.value_changed.connect(_on_scale)
	_on_scale(scale_slider.value, false)
	var sub_row := HBoxContainer.new()
	sub_row.add_theme_constant_override("separation", 10)
	v.add_child(sub_row)
	var subl := UiStyle.label("Subtitles", 15, UiStyle.HUD_DIM, true)
	subl.add_theme_font_override("font", UiStyle.font("display600", 2))
	subl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sub_row.add_child(subl)
	subtitles_button = Button.new()
	subtitles_button.toggle_mode = true
	subtitles_button.focus_mode = Control.FOCUS_NONE
	subtitles_button.custom_minimum_size.x = 72
	subtitles_button.button_pressed = Subtitles.enabled()
	subtitles_button.text = "ON" if subtitles_button.button_pressed else "OFF"
	subtitles_button.toggled.connect(func(on: bool):
		Subtitles.set_enabled(on)
		subtitles_button.text = "ON" if on else "OFF")
	sub_row.add_child(subtitles_button)
	panel.visible = false


func _on_scale(v: float, save := true) -> void:
	scale_value.text = "%d%%" % roundi(v * 100.0)
	if save:
		UiStyle.set_hud_scale(v)


func _set_buttons(items: Array) -> void:
	for c in buttons.get_children():
		c.queue_free()
	for it in items:
		var b := Button.new()
		b.text = it[0]
		b.pressed.connect(it[1])
		buttons.add_child(b)


func open_pause() -> void:
	if ended:
		return
	title.text = "PAUSED"
	title.add_theme_color_override("font_color", UiStyle.HUD_INK)
	scale_row.visible = true
	_set_buttons([["Resume", close], ["Paint scheme", _toggle_paint], ["Restart mission", _restart], ["Abort to briefing", _abort]])
	panel.visible = true
	get_tree().paused = true


var _paint: PaintPanel


## The player's paint scheme, live on the player's units (PaintPanel; saved to user://settings.cfg [paint]).
func _toggle_paint() -> void:
	if _paint:
		_paint.queue_free()
		_paint = null
		return
	_paint = PaintPanel.new(BayKit.new(UiStyle.hud_unit(1080.0, 1.0) * 0.85))
	_paint.changed.connect(func(_s): if view and view.has_method("repaint_player"): view.repaint_player())
	panel.get_child(0).add_child(_paint)


func close() -> void:
	if _paint:
		_paint.queue_free()
		_paint = null
	panel.visible = false
	get_tree().paused = false


func show_end(won: bool) -> void:
	ended = true
	title.text = "MISSION SUCCESSFUL" if won else "MISSION FAILED"
	title.add_theme_color_override("font_color", UiStyle.HUD_OK if won else UiStyle.HUD_CRIT)
	scale_row.visible = false
	_set_buttons([["Continue to debrief", _continue], ["Replay mission", _restart]])
	panel.visible = true


func _continue() -> void:
	get_tree().paused = false
	Flow.mission_finished(view.report())


func _restart() -> void:
	get_tree().paused = false
	Flow.current = view.mission
	Flow.launch()


func _abort() -> void:
	get_tree().paused = false
	Flow.goto_briefing(view.mission)


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	if event.keycode == KEY_ESCAPE:
		if view.flyby and not view.flyby._done:
			return  # the flyby takes Esc as "skip"
		if view.input and view.input.support_kind != "":
			return  # Esc cancels support targeting first
		if ended:
			return
		if panel.visible:
			close()
		else:
			open_pause()
		get_viewport().set_input_as_handled()
	elif event.keycode in [KEY_ENTER, KEY_KP_ENTER] and ended:
		_continue()
		get_viewport().set_input_as_handled()
