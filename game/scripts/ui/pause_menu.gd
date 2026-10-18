class_name PauseMenu
extends CanvasLayer
## In-mission overlay. Esc pauses: Resume / Restart mission / Abort to briefing.
## When the mission ends the same panel offers Continue (to the debrief) and Replay;
## Enter continues.

var view: Node  # MissionView
var panel: PanelContainer
var title: Label
var buttons: VBoxContainer
var ended := false


func _ready() -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.theme = UiStyle.theme()
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(340, 0)
	center.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	panel.add_child(v)
	title = UiStyle.label("Paused", 26, UiStyle.TEXT, true)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(title)
	buttons = VBoxContainer.new()
	buttons.add_theme_constant_override("separation", 8)
	v.add_child(buttons)
	panel.visible = false


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
	title.add_theme_color_override("font_color", UiStyle.TEXT)
	_set_buttons([["Resume", close], ["Restart mission", _restart], ["Abort to briefing", _abort]])
	panel.visible = true
	get_tree().paused = true


func close() -> void:
	panel.visible = false
	get_tree().paused = false


func show_end(won: bool) -> void:
	ended = true
	title.text = "MISSION SUCCESSFUL" if won else "MISSION FAILED"
	title.add_theme_color_override("font_color", UiStyle.ACCENT if won else UiStyle.FAIL)
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
