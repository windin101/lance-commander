class_name UiStyle
extends RefCounted
## Shared look for the between-mission screens: a dark command console with the HUD's
## green accent. theme() is applied to each screen's root Control.

const BG := Color(0.035, 0.05, 0.055)
const PANEL := Color(0.065, 0.09, 0.095, 0.95)
const PANEL_EDGE := Color(0.2, 0.42, 0.27)
const ACCENT := Color(0.45, 1.0, 0.55)
const TEXT := Color(0.86, 0.92, 0.87)
const DIM := Color(0.55, 0.64, 0.58)
const WARN := Color(1.0, 0.76, 0.32)
const FAIL := Color(1.0, 0.42, 0.32)

static var _theme: Theme


static func theme() -> Theme:
	if _theme:
		return _theme
	var t := Theme.new()
	t.default_font_size = 16
	t.set_color("font_color", "Label", TEXT)
	t.set_color("default_color", "RichTextLabel", TEXT)
	t.set_stylebox("panel", "PanelContainer", _box(PANEL, PANEL_EDGE, 1, 14))
	t.set_stylebox("panel", "Panel", _box(PANEL, PANEL_EDGE, 1, 0))
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var fill := Color(0.09, 0.14, 0.11)
		var edge := PANEL_EDGE
		match state:
			"hover":
				fill = Color(0.12, 0.22, 0.15)
				edge = ACCENT
			"pressed":
				fill = Color(0.18, 0.34, 0.22)
				edge = ACCENT
			"disabled":
				fill = Color(0.06, 0.07, 0.07)
				edge = Color(0.2, 0.22, 0.21)
			"focus":
				fill = Color(0, 0, 0, 0)
				edge = ACCENT
		t.set_stylebox(state, "Button", _box(fill, edge, 1, 0, Vector4(18, 8, 18, 8)))
	t.set_color("font_color", "Button", TEXT)
	t.set_color("font_hover_color", "Button", ACCENT)
	t.set_color("font_pressed_color", "Button", ACCENT)
	t.set_color("font_disabled_color", "Button", Color(0.38, 0.42, 0.4))
	t.set_stylebox("scroll", "VScrollBar", _box(Color(0.05, 0.07, 0.07), Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber", "VScrollBar", _box(Color(0.2, 0.36, 0.25), Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_highlight", "VScrollBar", _box(Color(0.3, 0.55, 0.36), Color(0, 0, 0, 0), 0, 0))
	_theme = t
	return t


static func _box(fill: Color, edge: Color, border: int, pad: int, margins := Vector4(-1, -1, -1, -1)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.border_color = edge
	s.set_border_width_all(border)
	if margins.x >= 0:
		s.content_margin_left = margins.x
		s.content_margin_top = margins.y
		s.content_margin_right = margins.z
		s.content_margin_bottom = margins.w
	else:
		s.set_content_margin_all(pad)
	return s


## A label in one call: size, colour, optional caps.
static func label(text: String, size := 16, colour := TEXT, caps := false) -> Label:
	var l := Label.new()
	l.text = text.to_upper() if caps else text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	return l


## A section heading: small caps in the accent colour with a rule under it.
static func heading(text: String) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	var l := label(text, 13, ACCENT, true)
	l.add_theme_constant_override("line_spacing", 0)
	v.add_child(l)
	var rule := ColorRect.new()
	rule.color = PANEL_EDGE
	rule.custom_minimum_size = Vector2(0, 1)
	v.add_child(rule)
	return v


## Objective strings carry their own "1. " numbering; screens number them themselves.
static func objective_title(title: String) -> String:
	var t := title.strip_edges()
	var dot := t.find(". ")
	return t.substr(dot + 2) if dot >= 0 and dot <= 3 and t.left(dot).is_valid_int() else t


## Original text shown on screen: Microsoft's trademark stays out of the game (licence
## ground rules); "MechCommander" in the briefings becomes our title.
static func clean(text: String) -> String:
	return text.replace("MechCommander", "Lance Commander").replace("Mechcommander", "Lance Commander")


static func backdrop(root: Control) -> void:
	var bg := ColorRect.new()
	bg.color = BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(bg)
	root.move_child(bg, 0)
