class_name MainMenu
extends Control
## The main menu (style guide 5.1, amber layer): a slow 3D vignette (the player's lead 'Mech on the
## bay turntable, in the player scheme) under a heavy vignette, our own angular stencil logo
## top-left, the vertical menu on the left (Chakra Petch 28 caps; hover/focus = amber bar, glow and
## a 4 px indent), the version tag bottom-left in mono 11.
## New campaign resets progress and opens the first group's intro; Continue resumes at Flow.current.
## Skirmish and Options are not built yet and show disabled.

const VERSION_TAG := "LANCE COMMANDER · BUILD 0.1 · NON-COMMERCIAL"
const HERO_CHASSIS := "atlas"

var buttons := {}  # id -> Button
var stage: MechStage


func _ready() -> void:
	theme = StyleTokens.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiStyle.backdrop(self)
	_hero()
	add_child(Vignette.new())
	var m := StyleTokens.geo("outer_margin")
	var logo := Logo.new()
	logo.position = Vector2(m, m)
	add_child(logo)
	var menu := VBoxContainer.new()
	menu.name = "Menu"
	menu.add_theme_constant_override("separation", int(StyleTokens.geo("grid")))
	menu.anchor_top = 0.42
	menu.anchor_bottom = 0.42
	menu.offset_left = m - StyleTokens.geo("gutter")
	menu.offset_right = m + 420
	add_child(menu)
	var has_progress := not Flow.completed.is_empty()
	for e in [["new", "New campaign", true], ["continue", "Continue", has_progress], ["skirmish", "Skirmish", false],
			["options", "Options", false], ["exit", "Exit", true]]:
		var b := Button.new()
		b.name = String(e[0])
		b.theme_type_variation = "MainMenuItem"
		b.text = String(e[1]).to_upper()
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.disabled = not e[2]
		if not e[2] and e[0] in ["skirmish", "options"]:
			b.tooltip_text = "Not built yet"
		b.pressed.connect(_choose.bind(String(e[0])))
		menu.add_child(b)
		buttons[e[0]] = b
	var ver := StyleTokens.label(VERSION_TAG, "MicroLabel")
	ver.anchor_top = 1.0
	ver.anchor_bottom = 1.0
	ver.offset_left = m
	ver.offset_top = -m
	ver.offset_bottom = -m + 16
	add_child(ver)
	var first: Button = buttons["continue"] if has_progress else buttons["new"]
	first.grab_focus.call_deferred()
	StyleTokens.boot_flicker(self)
	for i in menu.get_child_count():
		StyleTokens.panel_in.call_deferred(menu.get_child(i), 0.1 + i * StyleTokens.motion_s("hud_stagger"), Vector2(-1, 0))


func _hero() -> void:
	stage = MechStage.new()
	stage.name = "Hero"
	stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stage.anchor_left = 0.34
	stage.anchor_right = 1.0
	stage.anchor_top = 0.04
	stage.anchor_bottom = 1.0
	add_child(stage)
	stage.spin = 4.0  # degrees per second: a slow drydock turn
	stage.show_mech(HERO_CHASSIS, PaintScheme.player(), -32.0)


func _choose(id: String) -> void:
	match id:
		"new":
			Flow.new_campaign()
			get_tree().change_scene_to_file(Flow.INTRO)
		"continue":
			get_tree().change_scene_to_file(Flow.INTRO)
		"exit":
			get_tree().quit()


## Heavy vignette over the hero: the left third darkened for the menu, the edges falling to ink-900.
class Vignette:
	extends Control

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_preset(Control.PRESET_FULL_RECT)

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var ink := UiStyle.INK_900
		var clear := Color(ink, 0.0)
		# left: solid for the menu, fading out by 55 % of the width
		draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w * 0.55, 0), Vector2(w * 0.55, h), Vector2(0, h)]),
			PackedColorArray([Color(ink, 0.92), clear, clear, Color(ink, 0.92)]))
		# top and bottom bands
		draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h * 0.22), Vector2(0, h * 0.22)]),
			PackedColorArray([Color(ink, 0.85), Color(ink, 0.85), clear, clear]))
		draw_polygon(PackedVector2Array([Vector2(0, h * 0.7), Vector2(w, h * 0.7), Vector2(w, h), Vector2(0, h)]),
			PackedColorArray([clear, clear, Color(ink, 0.95), Color(ink, 0.95)]))
		# right edge
		draw_polygon(PackedVector2Array([Vector2(w * 0.85, 0), Vector2(w, 0), Vector2(w, h), Vector2(w * 0.85, h)]),
			PackedColorArray([clear, Color(ink, 0.8), Color(ink, 0.8), clear]))
		# faint scanlines (4 % opacity)
		var sc := Color(StyleTokens.color("steel-100"), StyleTokens.alpha("hatch") * 0.5)
		var y := 0.0
		while y < h:
			draw_line(Vector2(0, y), Vector2(w, y), sc, 1.0)
			y += 4.0


## Our own angular stencil logo: a chamfered amber chevron mark and the title in Chakra Petch caps.
class Logo:
	extends Control

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		custom_minimum_size = Vector2(620, 96)
		size = custom_minimum_size

	func _draw() -> void:
		var amber := UiStyle.AMBER_500
		var s := 64.0
		# the mark: a chamfered square frame, two stacked chevrons inside (a lance's rank marks)
		var frame := StyleTokens.ChamferBox.outline(Rect2(0, 0, s, s), 12.0)
		frame.append(frame[0])
		draw_polyline(frame, amber, 3.0)
		for k in 2:
			var y0 := 18.0 + k * 16.0
			draw_colored_polygon(PackedVector2Array([Vector2(14, y0), Vector2(32, y0 + 10), Vector2(50, y0),
				Vector2(50, y0 + 7), Vector2(32, y0 + 17), Vector2(14, y0 + 7)]), amber)
		var title_f := StyleTokens.font("display", 40, true)
		draw_string(title_f, Vector2(s + 20, 36), "LANCE COMMANDER", HORIZONTAL_ALIGNMENT_LEFT, -1, 40, UiStyle.WHITE)
		var sub_f := StyleTokens.font("label", 13)
		draw_string(sub_f, Vector2(s + 22, 60), "BATTLE FOR THE SPHERE", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, UiStyle.STEEL_300)
		draw_line(Vector2(s + 22, 70), Vector2(s + 300, 70), UiStyle.STEEL_500, 1.0)
