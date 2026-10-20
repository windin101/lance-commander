class_name UiStyle
extends RefCounted
## Shared look for the between-mission screens: a dark command console with the HUD's
## green accent. theme() is applied to each screen's root Control.
##
## The in-mission HUD has its own look (Lee's approved mock-up, 2026-10-20): cyan-framed
## command panels with bevelled corners, Chakra Petch / Barlow Semi Condensed / Share Tech
## Mono (OFL, assets/fonts). Its sizes are in a base unit, hud_unit(), that follows the
## viewport height and the player's HUD scale setting; hud_theme(unit) and HudFrame build it.

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


# ---------------------------------------------------------------- in-mission HUD

# Colour tokens of the approved HUD mock-up (hudmock/template.html :root).
const HUD_INK := Color(0.910, 0.945, 0.957)  # #e8f1f4 primary text
const HUD_DIM := Color(0.561, 0.651, 0.698)  # #8fa6b2 secondary text
const HUD_PANEL := Color(9 / 255.0, 20 / 255.0, 30 / 255.0, 0.80)
const HUD_PANEL_2 := Color(16 / 255.0, 33 / 255.0, 46 / 255.0, 0.86)
const HUD_EDGE := Color(0.247, 0.776, 0.878)  # #3fc6e0 cyan frame line
const HUD_EDGE_SOFT := Color(0.247, 0.776, 0.878, 0.35)
const HUD_GLOW := Color(0.247, 0.776, 0.878, 0.45)
const HUD_OK := Color(0.310, 0.827, 0.541)  # #4fd38a
const HUD_WARN := Color(0.949, 0.710, 0.290)  # #f2b54a
const HUD_CRIT := Color(1.0, 0.353, 0.306)  # #ff5a4e
const HUD_HOT := Color(1.0, 0.478, 0.184)  # #ff7a2f
const HUD_FACE := Color(0.055, 0.114, 0.157)  # #0e1d28 portrait well
# Weapon range colours (short / medium / long), as the original's info tab.
const RANGE_COLOURS := {"short": Color(0.608, 0.749, 0.180), "medium": Color(0.184, 0.561, 0.827), "long": Color(0.824, 0.290, 0.165)}

const HUD_SCALE_DEFAULT := 0.7
const HUD_SCALE_MIN := 0.6
const HUD_SCALE_MAX := 1.0
const SETTINGS_PATH := "user://settings.cfg"
## The mock-up's 1em: 0.85% of the frame width. At the 1080-high reference that frame is
## 1920 wide, so 16.32 px at scale 1.0, 11.4 px at the default 0.7.
const HUD_UNIT_REF := 0.0085 * 1920.0

const FONT_FILES := {
	"display500": "res://assets/fonts/chakra_petch/ChakraPetch-Medium.ttf",
	"display600": "res://assets/fonts/chakra_petch/ChakraPetch-SemiBold.ttf",
	"display700": "res://assets/fonts/chakra_petch/ChakraPetch-Bold.ttf",
	"body400": "res://assets/fonts/barlow_semi_condensed/BarlowSemiCondensed-Regular.ttf",
	"body500": "res://assets/fonts/barlow_semi_condensed/BarlowSemiCondensed-Medium.ttf",
	"body600": "res://assets/fonts/barlow_semi_condensed/BarlowSemiCondensed-SemiBold.ttf",
	"mono": "res://assets/fonts/share_tech_mono/ShareTechMono-Regular.ttf",
}

static var _fonts := {}
static var _hud_scale := -1.0


## A HUD font by role and weight ("display600", "body400", "mono"...); with spacing_px > 0,
## a FontVariation with that letter spacing (the mock-up's letter-spacing). Falls back to
## Godot's default font if the file is missing.
static func font(kind: String, spacing_px := 0) -> Font:
	var key := "%s/%d" % [kind, spacing_px]
	if _fonts.has(key):
		return _fonts[key]
	var f: Font = null
	if spacing_px > 0:
		var v := FontVariation.new()
		v.base_font = font(kind)
		v.spacing_glyph = spacing_px
		f = v
	else:
		var path: String = FONT_FILES.get(kind, "")
		if not path.is_empty() and ResourceLoader.exists(path):
			f = load(path)
		if f == null:
			f = ThemeDB.fallback_font
	_fonts[key] = f
	return f


## The player's HUD scale (0.6-1.0, default 0.7), kept in user://settings.cfg [hud] scale.
static func hud_scale() -> float:
	if _hud_scale < 0.0:
		var cfg := ConfigFile.new()
		var v := HUD_SCALE_DEFAULT
		if cfg.load(SETTINGS_PATH) == OK:
			v = float(cfg.get_value("hud", "scale", HUD_SCALE_DEFAULT))
		_hud_scale = clampf(v, HUD_SCALE_MIN, HUD_SCALE_MAX)
	return _hud_scale


static func set_hud_scale(v: float, save := true) -> void:
	_hud_scale = clampf(v, HUD_SCALE_MIN, HUD_SCALE_MAX)
	if not save:
		return
	var cfg := ConfigFile.new()
	cfg.load(SETTINGS_PATH)
	cfg.set_value("hud", "scale", _hud_scale)
	cfg.save(SETTINGS_PATH)


## The HUD base unit in pixels for a viewport height: scale = height / 1080 * HUD scale.
static func hud_unit(viewport_height: float, scale := -1.0) -> float:
	return HUD_UNIT_REF * viewport_height / 1080.0 * (hud_scale() if scale < 0.0 else scale)


## Theme for the HUD at base unit u: body font, cyan buttons, panel frames, slider.
static func hud_theme(u: float) -> Theme:
	var t := Theme.new()
	t.default_font = font("body400")
	t.default_font_size = roundi(u * 1.1)
	t.set_color("font_color", "Label", HUD_INK)
	t.set_stylebox("panel", "PanelContainer", HudFrame.make(u))
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var fill := Color(HUD_EDGE, 0.08)
		var edge := HUD_EDGE_SOFT
		match state:
			"hover":
				fill = Color(HUD_EDGE, 0.18)
				edge = HUD_EDGE
			"pressed":
				fill = Color(HUD_EDGE, 0.28)
				edge = HUD_EDGE
			"disabled":
				fill = Color(1, 1, 1, 0.03)
				edge = Color(HUD_EDGE_SOFT, 0.15)
			"focus":
				fill = Color(0, 0, 0, 0)
				edge = HUD_EDGE
		var b := _box(fill, edge, 1, 0, Vector4(u * 0.6, u * 0.3, u * 0.6, u * 0.3))
		t.set_stylebox(state, "Button", b)
	t.set_font("font", "Button", font("display600", roundi(u * 0.08)))
	t.set_font_size("font_size", "Button", roundi(u * 0.95))
	t.set_color("font_color", "Button", HUD_INK)
	t.set_color("font_hover_color", "Button", HUD_INK)
	t.set_color("font_pressed_color", "Button", HUD_INK)
	t.set_color("font_disabled_color", "Button", Color(HUD_DIM, 0.5))
	var track := _box(Color(1, 1, 1, 0.08), Color(0, 0, 0, 0), 0, 0)
	track.content_margin_top = u * 0.2
	track.content_margin_bottom = u * 0.2
	t.set_stylebox("slider", "HSlider", track)
	t.set_stylebox("grabber_area", "HSlider", _box(HUD_EDGE, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_area_highlight", "HSlider", _box(HUD_EDGE, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("scroll", "VScrollBar", _box(Color(1, 1, 1, 0.04), Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber", "VScrollBar", _box(HUD_EDGE_SOFT, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_highlight", "VScrollBar", _box(HUD_EDGE, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_pressed", "VScrollBar", _box(HUD_EDGE, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	return t


## The HUD panel frame (the mock-up's .p): dark fill clipped to bevelled top-left and
## bottom-right corners, a soft cyan outline, and bright cyan brackets on the two bevels.
class HudFrame:
	extends StyleBox

	var fill := HUD_PANEL
	var edge := HUD_EDGE_SOFT
	var bracket := HUD_EDGE
	var cut := 10.0  # bevel size (0.9 em)
	var arm := 30.0  # bracket arm length (2.6 em)
	var line := 2.0  # bracket thickness

	static func make(u: float, pad := Vector4(0, 0, 0, 0)) -> HudFrame:
		var f := HudFrame.new()
		f.cut = maxf(4.0, u * 0.9)
		f.arm = maxf(10.0, u * 2.6)
		f.line = maxf(1.0, roundf(u * 0.16))
		f.content_margin_left = pad.x
		f.content_margin_top = pad.y
		f.content_margin_right = pad.z
		f.content_margin_bottom = pad.w
		return f

	func _draw(to_canvas_item: RID, rect: Rect2) -> void:
		var p := rect.position
		var w := rect.size.x
		var h := rect.size.y
		var c := minf(cut, minf(w, h) * 0.3)
		var poly := PackedVector2Array([p + Vector2(c, 0), p + Vector2(w, 0), p + Vector2(w, h - c),
			p + Vector2(w - c, h), p + Vector2(0, h), p + Vector2(0, c)])
		RenderingServer.canvas_item_add_polygon(to_canvas_item, poly, PackedColorArray([fill]))
		var outline := poly.duplicate()
		outline.append(poly[0])
		RenderingServer.canvas_item_add_polyline(to_canvas_item, outline, PackedColorArray([edge]), 1.0)
		var a := minf(arm, minf(w, h) * 0.5)
		var o := line * 0.5
		RenderingServer.canvas_item_add_polyline(to_canvas_item, PackedVector2Array([
			p + Vector2(o, a), p + Vector2(o, c), p + Vector2(c, o), p + Vector2(a, o)]), PackedColorArray([bracket]), line)
		RenderingServer.canvas_item_add_polyline(to_canvas_item, PackedVector2Array([
			p + Vector2(w - o, h - a), p + Vector2(w - o, h - c), p + Vector2(w - c, h - o), p + Vector2(w - a, h - o)]),
			PackedColorArray([bracket]), line)
