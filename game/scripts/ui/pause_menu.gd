class_name PauseMenu
extends CanvasLayer
## In-mission overlay (style guide 5.12, a 4.3 modal in the amber layer): Esc pauses; the scene is dimmed to 55 %
## and blurred, and a centred amber-framed panel with a section-tag title bar offers Resume / Paint scheme /
## Restart mission / Abort mission, then the options: HUD scale (0.6-1.0, saved to user://settings.cfg; the
## HUD rebuilds at the new size), comms subtitles and reduce motion (4.4). When the mission ends the same
## panel offers Continue (to the debrief) and Replay; Enter continues.
## Dev: --paused opens it at start (screenshots).

const DIM_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float dim = 0.55;
uniform float blur_lod = 2.6;  // about a 6 px blur at 1080p
void fragment() {
	COLOR = vec4(textureLod(screen_tex, SCREEN_UV, blur_lod).rgb * (1.0 - dim), 1.0);
}
"""

var view: Node  # MissionView
var panel: PanelContainer
var title: Label
var buttons: VBoxContainer
var ended := false
var scale_row: HBoxContainer
var scale_slider: HSlider
var scale_value: Label
var subtitles_button: Button  # comms subtitles on/off (Subtitles, user://settings.cfg [comms])
var motion_button: Button  # reduce motion on/off (StyleTokens, user://settings.cfg [accessibility])
var options: VBoxContainer
var _dim: ColorRect
var _kit: BayKit


func _ready() -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	var u := UiStyle.hud_unit(1080.0, 1.0) * 0.85
	_kit = BayKit.new(u)
	_kit.set_amber()
	root.theme = UiStyle.hud_theme(u, true)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_dim = ColorRect.new()
	_dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_dim.mouse_filter = Control.MOUSE_FILTER_STOP  # the scene behind takes no clicks while paused
	var mat := ShaderMaterial.new()
	mat.shader = Shader.new()
	mat.shader.code = DIM_SHADER
	mat.set_shader_parameter("dim", StyleTokens.alpha("modal-dim"))
	_dim.material = mat
	_dim.visible = false
	root.add_child(_dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(u * 30.0, 0)
	var frame := StyleTokens.ChamferBox.make(Color(UiStyle.INK_700, 0.95), UiStyle.AMBER_500, 2, maxf(6.0, u * 1.2),
		Vector4(3, 3, 3, u * 1.4), true)
	frame.bracket = maxf(8.0, u * 1.05)
	frame.bracket_colour = UiStyle.AMBER_300
	panel.add_theme_stylebox_override("panel", frame)
	center.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", roundi(u * 1.0))
	panel.add_child(v)
	# section-tag title bar: a raised strip with the tag and the title
	var bar := PanelContainer.new()
	var bs := StyleBoxFlat.new()
	bs.bg_color = UiStyle.INK_600
	bs.border_color = UiStyle.AMBER_700
	bs.border_width_bottom = 1
	bs.content_margin_left = u * 1.4
	bs.content_margin_right = u * 1.4
	bs.content_margin_top = u * 0.9
	bs.content_margin_bottom = u * 0.7
	bar.add_theme_stylebox_override("panel", bs)
	v.add_child(bar)
	var bv := VBoxContainer.new()
	bv.add_theme_constant_override("separation", 2)
	bar.add_child(bv)
	bv.add_child(_kit.label("Command · mission hold", "display600", 0.8, UiStyle.AMBER_500, true, 0.14))
	title = UiStyle.label("Paused", roundi(u * 2.2), UiStyle.WHITE, true)
	title.add_theme_font_override("font", StyleTokens.font("display", roundi(u * 2.2), true))
	bv.add_child(title)
	var body := _kit.margin(1.4, 0.2, 1.4, 0)
	v.add_child(body)
	var bvb := VBoxContainer.new()
	bvb.add_theme_constant_override("separation", roundi(u * 1.0))
	body.add_child(bvb)
	buttons = VBoxContainer.new()
	buttons.add_theme_constant_override("separation", roundi(u * 0.6))
	bvb.add_child(buttons)
	options = VBoxContainer.new()
	options.add_theme_constant_override("separation", roundi(u * 0.6))
	bvb.add_child(options)
	options.add_child(_kit.label("Options", "display600", 0.85, UiStyle.AMBER_500, true, 0.14))
	options.add_child(_kit.rule())
	scale_row = HBoxContainer.new()
	scale_row.add_theme_constant_override("separation", 10)
	options.add_child(scale_row)
	var sl := _kit.label("HUD scale", "body600", 1.0, UiStyle.STEEL_300, true, 0.06)
	sl.custom_minimum_size.x = u * 10.0
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
	scale_value = _kit.label("", "mono", 1.0, UiStyle.STEEL_100)
	scale_value.custom_minimum_size.x = 44
	scale_value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	scale_row.add_child(scale_value)
	scale_slider.value_changed.connect(_on_scale)
	_on_scale(scale_slider.value, false)
	subtitles_button = _toggle_row("Subtitles", Subtitles.enabled(), func(on: bool): Subtitles.set_enabled(on))
	motion_button = _toggle_row("Reduce motion", StyleTokens.reduce_motion(), func(on: bool): StyleTokens.set_reduce_motion(on))
	panel.visible = false
	if OS.get_cmdline_user_args().has("--paused"):  # dev: screenshot the pause menu
		open_pause.call_deferred()


## An options row: caps label left, a square ON / OFF toggle right (4.3 toggles are square).
func _toggle_row(text: String, on: bool, apply: Callable) -> Button:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	options.add_child(row)
	var l := _kit.label(text, "body600", 1.0, UiStyle.STEEL_300, true, 0.06)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(l)
	var b := Button.new()
	b.toggle_mode = true
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size.x = 72
	b.button_pressed = on
	b.text = "ON" if on else "OFF"
	b.toggled.connect(func(v: bool):
		apply.call(v)
		b.text = "ON" if v else "OFF")
	row.add_child(b)
	return b


func _on_scale(v: float, save := true) -> void:
	scale_value.text = "%d%%" % roundi(v * 100.0)
	if save:
		UiStyle.set_hud_scale(v)


func _set_buttons(items: Array) -> void:
	for c in buttons.get_children():
		c.queue_free()
	for i in items.size():
		var b := Button.new()
		b.text = String(items[i][0]).to_upper()
		b.pressed.connect(items[i][1])
		if i == 0:
			_kit.primary(b)
		buttons.add_child(b)


func open_pause() -> void:
	if ended:
		return
	title.text = "PAUSED"
	title.add_theme_color_override("font_color", UiStyle.WHITE)
	options.visible = true
	_set_buttons([["Resume", close], ["Paint scheme", _toggle_paint], ["Restart mission", _restart], ["Abort mission", _abort]])
	panel.visible = true
	_dim.visible = true
	StyleTokens.fade_in(panel)
	get_tree().paused = true


var _paint: PaintPanel


## The player's paint scheme, live on the player's units (PaintPanel; saved to user://settings.cfg [paint]).
func _toggle_paint() -> void:
	if _paint:
		_paint.queue_free()
		_paint = null
		return
	_paint = PaintPanel.new(_kit)
	_paint.changed.connect(func(_s): if view and view.has_method("repaint_player"): view.repaint_player())
	panel.get_child(0).add_child(_paint)


func close() -> void:
	if _paint:
		_paint.queue_free()
		_paint = null
	panel.visible = false
	_dim.visible = false
	get_tree().paused = false


func show_end(won: bool) -> void:
	ended = true
	title.text = "MISSION SUCCESSFUL" if won else "MISSION FAILED"
	title.add_theme_color_override("font_color", UiStyle.STATE_OK if won else UiStyle.CRIT)
	options.visible = false
	_set_buttons([["Continue to debrief", _continue], ["Replay mission", _restart]])
	panel.visible = true
	_dim.visible = true


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
