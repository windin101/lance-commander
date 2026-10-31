class_name UiStyle
extends RefCounted
## Shared look for the between-mission screens (the amber layer of docs/art/STYLE-GUIDE.md 2.1:
## menus, campaign, mech bay, debrief). theme() is StyleTokens.theme(), built from
## res://data/theme/style_tokens.json; the constants below mirror those tokens for code that
## colours single labels (style_tokens_test pins them to the JSON). Green is reserved for `ok`.
##
## The in-mission HUD has its own look (Lee's approved mock-up, 2026-10-20, the guide's 6): cyan-framed
## command panels with bevelled corners, Chakra Petch / Barlow Semi Condensed / Share Tech
## Mono (OFL, assets/fonts). Its sizes are in a base unit, hud_unit(), that follows the
## viewport height and the player's HUD scale setting; hud_theme(unit) and HudFrame build it.

# Section 2.1 tokens (names as the guide's, - -> _).
const INK_900 := Color("#070A0D")
const INK_800 := Color("#0C1117")
const INK_700 := Color("#121A22")
const INK_600 := Color("#1B2630")
const STEEL_500 := Color("#3A4854")
const STEEL_300 := Color("#7F909C")
const STEEL_100 := Color("#D5DEE3")
const WHITE := Color("#F2F6F8")
const AMBER_500 := Color("#F2A21F")
const AMBER_300 := Color("#FFC85A")
const AMBER_700 := Color("#8C5A0C")
const CYAN_400 := Color("#3FC6E0")
const STATE_OK := Color("#4FD38A")  # token `ok` (OK itself is the Error enum)
const WARN := Color("#F2B54A")
const HEAT := Color("#FF7A2F")
const CRIT := Color("#FF5A4E")
const FRIEND := Color("#5CA0FF")
const NEUTRAL := Color("#C9CED2")

# The older between-mission names, now on the tokens (the old green accent is gone, guide 19.1).
const BG := INK_800
const PANEL := Color(INK_700, 0.85)
const PANEL_EDGE := STEEL_500
const ACCENT := AMBER_500
const TEXT := STEEL_100
const DIM := STEEL_300
const FAIL := CRIT


static func theme() -> Theme:
	return StyleTokens.theme()


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


## A section heading (4.3 table header): label-role caps in amber over a 1 px steel-500 rule.
static func heading(text: String) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	var l := label(text, StyleTokens.size("label"), ACCENT, true)
	l.add_theme_font_override("font", StyleTokens.font("label", StyleTokens.size("label")))
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

# The HUD's colours on the guide's tokens (6: thin cyan line-work at 80 % alpha with a 40 % glow, panels
# ink-700 at 80 %). HUD_INK, HUD_DIM and HUD_FACE are kept as the guide's 19.2 lists them; the rest are the 2.1
# tokens under their HUD names, kept as aliases for code not yet renamed (new code uses the token names).
const HUD_INK := Color("#E8F1F4")  # primary HUD text (19.2, kept)
const HUD_DIM := Color("#8FA6B2")  # secondary HUD text (19.2, kept)
const PORTRAIT_WELL := Color("#0E1D28")  # 6 lance cards, 7 portraits
const CYAN_LINE := Color(CYAN_400, 0.80)  # HUD frame line-work (6)
const CYAN_GLOW := Color(CYAN_400, 0.40)  # glow on HUD lines (2.1 cyan-glow)
const CYAN_RULE := Color(CYAN_400, 0.35)  # dividers inside HUD panels
const HUD_PANEL := Color(INK_700, 0.80)  # 6: panels ink-700 at 80 %
const HUD_PANEL_2 := Color(INK_600, 0.86)  # raised: a header strip, a value box
const HUD_EDGE := CYAN_400
const HUD_EDGE_SOFT := CYAN_RULE
const HUD_GLOW := CYAN_GLOW
const HUD_OK := STATE_OK
const HUD_WARN := WARN
const HUD_CRIT := CRIT
const HUD_HOT := HEAT
const HUD_FACE := PORTRAIT_WELL
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


## Theme for the HUD at base unit u: body font, cyan buttons, panel frames, slider. amber: the same sizes in the
## amber layer (briefing, mech bay, mech lab, pause; guide 2.1, 4.3): chamfered steel-framed panels, steel
## secondary buttons (BayKit.primary makes the amber primary one), amber slider and scroll grabbers.
static func hud_theme(u: float, amber := false) -> Theme:
	var t := Theme.new()
	var accent := AMBER_500 if amber else CYAN_400
	var ink := STEEL_100 if amber else HUD_INK
	var dim := STEEL_300 if amber else HUD_DIM
	t.default_font = font("body400")
	t.default_font_size = roundi(u * 1.1)
	t.set_color("font_color", "Label", ink)
	t.set_color("default_color", "RichTextLabel", ink)
	if amber:
		var cut := maxf(4.0, u * 0.9)
		t.set_stylebox("panel", "PanelContainer", StyleTokens.ChamferBox.make(Color(INK_700, 0.85), STEEL_500, 1, cut, Vector4.ZERO, true))
		var c6 := maxf(3.0, u * 0.5)
		var m := Vector4(u * 0.6, u * 0.3, u * 0.6, u * 0.3)
		t.set_stylebox("normal", "Button", StyleTokens.ChamferBox.make(INK_700, STEEL_300, 1, c6, m))
		t.set_stylebox("hover", "Button", StyleTokens.ChamferBox.make(INK_600, STEEL_100, 1, c6, m))
		t.set_stylebox("pressed", "Button", StyleTokens.ChamferBox.make(AMBER_700, AMBER_300, 1, c6, m))
		t.set_stylebox("hover_pressed", "Button", StyleTokens.ChamferBox.make(AMBER_700, AMBER_300, 1, c6, m))
		t.set_stylebox("disabled", "Button", StyleTokens.ChamferBox.make(INK_800, STEEL_500, 1, c6, m))
		t.set_stylebox("focus", "Button", StyleTokens.ChamferBox.make(Color(0, 0, 0, 0), AMBER_300, 1, c6, Vector4.ZERO))
		t.set_color("font_color", "Button", dim)
		t.set_color("font_hover_color", "Button", WHITE)
		t.set_color("font_pressed_color", "Button", WHITE)
		t.set_color("font_hover_pressed_color", "Button", WHITE)
		t.set_color("font_focus_color", "Button", dim)
		t.set_color("font_disabled_color", "Button", STEEL_500)
		t.set_font("font", "Button", StyleTokens.font("label", roundi(u * 0.95)))
	else:
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
		t.set_color("font_color", "Button", HUD_INK)
		t.set_color("font_hover_color", "Button", HUD_INK)
		t.set_color("font_pressed_color", "Button", HUD_INK)
		t.set_color("font_disabled_color", "Button", Color(HUD_DIM, 0.5))
	t.set_font_size("font_size", "Button", roundi(u * 0.95))
	var track := _box(INK_600 if amber else Color(1, 1, 1, 0.08), Color(0, 0, 0, 0), 0, 0)
	track.content_margin_top = u * 0.2
	track.content_margin_bottom = u * 0.2
	t.set_stylebox("slider", "HSlider", track)
	t.set_stylebox("grabber_area", "HSlider", _box(accent, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_area_highlight", "HSlider", _box(accent, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("scroll", "VScrollBar", _box(Color(1, 1, 1, 0.04), Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber", "VScrollBar", _box(STEEL_500 if amber else HUD_EDGE_SOFT, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_highlight", "VScrollBar", _box(accent, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("grabber_pressed", "VScrollBar", _box(accent, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	var tip := _box(Color(INK_900, 0.95), STEEL_500, 1, 8)
	t.set_stylebox("panel", "TooltipPanel", tip)
	t.set_color("font_color", "TooltipLabel", ink)
	return t


## The HUD panel frame (the mock-up's .p): dark fill clipped to bevelled top-left and
## bottom-right corners, a soft cyan outline, and bright cyan brackets on the two bevels.
class HudFrame:
	extends StyleBox

	var fill := HUD_PANEL
	var edge := CYAN_LINE  # 6: line-work at 80 %
	var glow := Color(CYAN_GLOW, 0.12)  # a soft line under the outline (alpha 0 = none)
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
		if glow.a > 0.0:
			RenderingServer.canvas_item_add_polyline(to_canvas_item, outline, PackedColorArray([glow]), 3.0)
		RenderingServer.canvas_item_add_polyline(to_canvas_item, outline, PackedColorArray([edge]), 1.0)
		var a := minf(arm, minf(w, h) * 0.5)
		var o := line * 0.5
		RenderingServer.canvas_item_add_polyline(to_canvas_item, PackedVector2Array([
			p + Vector2(o, a), p + Vector2(o, c), p + Vector2(c, o), p + Vector2(a, o)]), PackedColorArray([bracket]), line)
		RenderingServer.canvas_item_add_polyline(to_canvas_item, PackedVector2Array([
			p + Vector2(w - o, h - a), p + Vector2(w - o, h - c), p + Vector2(w - c, h - o), p + Vector2(w - a, h - o)]),
			PackedColorArray([bracket]), line)
