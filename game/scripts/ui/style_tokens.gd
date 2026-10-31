class_name StyleTokens
extends RefCounted
## The master style guide's design tokens (docs/art/STYLE-GUIDE.md 2.1, 3, 4), loaded from
## res://data/theme/style_tokens.json, and the Godot Theme of the amber layer (menus, campaign,
## mech bay, debrief) built from them: chamfered thin-line frames, no rounded corners, no
## shadows. Screens set `theme = StyleTokens.theme()` and pick a role with
## theme_type_variation ("TitleLabel", "SectionLabel", "CapsLabel", "MonoLabel",
## "SecondaryButton", "MainMenuItem"...). The in-mission HUD keeps UiStyle.hud_theme (cyan, 6).

const PATH := "res://data/theme/style_tokens.json"

static var _data := {}
static var _theme: Theme
static var _fonts := {}


static func data() -> Dictionary:
	if _data.is_empty():
		var d = JSON.parse_string(FileAccess.get_file_as_string(PATH)) if FileAccess.file_exists(PATH) else null
		_data = d if d is Dictionary else {}
	return _data


## A colour token ("amber-500", "ink-700", "ok"...; also the colour_extra names), optionally with alpha.
static func color(name: String, alpha := -1.0) -> Color:
	var hex := String(data().get("colour", {}).get(name, data().get("colour_extra", {}).get(name, "")))
	if hex.is_empty():
		push_warning("StyleTokens: no colour token %s" % name)
		return Color.MAGENTA
	var c := Color(hex)
	if alpha >= 0.0:
		c.a = alpha
	return c


static func alpha(name: String) -> float:
	return float(data().get("alpha", {}).get(name, 1.0))


## A type-scale size in pixels at 1080p ("title", "section", "body", "label", "banner"...).
static func size(name: String) -> int:
	return int(data().get("type_scale", {}).get(name, 16))


static func geo(name: String) -> float:
	return float(data().get("geometry", {}).get(name, 0.0))


## A motion timing in seconds (tokens are milliseconds) or its raw value for non-time keys.
static func motion_s(name: String) -> float:
	return float(data().get("motion", {}).get(name, 0.0)) / 1000.0


## The font of a type role ("display", "body", "label", "numeric"); strong picks the heavier
## weight; px > 0 applies the role's tracking for that size.
static func font(role: String, px := 0, strong := false) -> Font:
	var r: Dictionary = data().get("type", {}).get(role, {})
	var key := String(r.get("strong", r.get("font", "body-400"))) if strong else String(r.get("font", "body-400"))
	var spacing := roundi(float(r.get("tracking", 0.0)) * px) if px > 0 else 0
	var ck := "%s/%d" % [key, spacing]
	if _fonts.has(ck):
		return _fonts[ck]
	var base: Font = null
	var path := String(data().get("font", {}).get(key, ""))
	if not path.is_empty() and ResourceLoader.exists(path):
		base = load(path)
	if base == null:
		base = ThemeDB.fallback_font
	var f: Font = base
	if spacing > 0:
		var v := FontVariation.new()
		v.base_font = base
		v.spacing_glyph = spacing
		f = v
	_fonts[ck] = f
	return f


static func caps(role: String) -> bool:
	return bool(data().get("type", {}).get(role, {}).get("caps", false))


## "Reduce motion" (4.4): user://settings.cfg [accessibility] reduce_motion. Off by default.
static var settings_path := UiStyle.SETTINGS_PATH  # tests point this elsewhere
static var _reduce := -1  # cached: -1 unread, 0 off, 1 on


static func reduce_motion() -> bool:
	if _reduce < 0:
		var cfg := ConfigFile.new()
		_reduce = 1 if cfg.load(settings_path) == OK and bool(cfg.get_value("accessibility", "reduce_motion", false)) else 0
	return _reduce == 1


## Turn "reduce motion" on or off; saved to user://settings.cfg [accessibility] unless save is false.
static func set_reduce_motion(on: bool, save := true) -> void:
	_reduce = 1 if on else 0
	if not save:
		return
	var cfg := ConfigFile.new()
	cfg.load(settings_path)
	cfg.set_value("accessibility", "reduce_motion", on)
	cfg.save(settings_path)


static func reset_cache() -> void:
	_data = {}
	_theme = null
	_fonts = {}


# ------------------------------------------------------------------------------- theme

static func theme() -> Theme:
	if _theme:
		return _theme
	var t := Theme.new()
	var body := size("body")
	var lab := size("label")
	t.default_font = font("body")
	t.default_font_size = body
	var text := color("steel-100")
	var dim := color("steel-300")
	var amber := color("amber-500")

	# labels by role
	t.set_color("font_color", "Label", text)
	t.set_constant("line_spacing", "Label", roundi(body * (1.35 - 1.0)))
	_label_type(t, "TitleLabel", font("display", size("title"), true), size("title"), color("white"))
	_label_type(t, "BannerLabel", font("display", size("banner"), true), size("banner"), color("white"))
	_label_type(t, "SectionLabel", font("display", size("section")), size("section"), amber)
	_label_type(t, "SubheadLabel", font("display", size("subhead")), size("subhead"), text)
	_label_type(t, "CapsLabel", font("label", lab), lab, dim)
	_label_type(t, "MonoLabel", font("numeric"), body, text)
	_label_type(t, "MicroLabel", font("numeric"), size("hud_micro"), dim)
	t.set_color("default_color", "RichTextLabel", text)
	t.set_font("normal_font", "RichTextLabel", font("body"))
	t.set_font("bold_font", "RichTextLabel", font("body", 0, true))

	# panels: ink-700 at 85 %, 1 px steel-500 frame, 10 px chamfer, faint hatch, top-edge highlight
	var cut := geo("chamfer_panel")
	var pad := geo("gutter")
	t.set_stylebox("panel", "PanelContainer", ChamferBox.make(color("ink-700", alpha("panel-fill")), color("steel-500"),
		geo("line_inactive"), cut, Vector4(pad, pad, pad, pad), true))
	t.set_stylebox("panel", "Panel", ChamferBox.make(color("ink-700", alpha("panel-fill")), color("steel-500"),
		geo("line_inactive"), cut, Vector4.ZERO, true))
	# a selected / focused panel: 2 px amber frame and 12 px corner brackets
	t.set_type_variation("ActivePanel", "PanelContainer")
	var act := ChamferBox.make(color("ink-700", alpha("panel-fill")), amber, geo("line_active"), cut,
		Vector4(pad, pad, pad, pad), true)
	act.bracket = geo("bracket")
	act.bracket_colour = color("amber-300")
	t.set_stylebox("panel", "ActivePanel", act)

	# primary button (4.3): amber 2 px frame, ink-700 fill, amber text; hover amber 15 % + glow;
	# pressed amber-700; disabled steel-500. Chamfer 6, min height 44.
	var c6 := geo("chamfer_small")
	var bm := Vector4(18, 11, 18, 11)
	var fill := color("ink-700")
	var hover_fill := fill.lerp(Color(amber, 1.0), alpha("button-hover-fill"))
	t.set_stylebox("normal", "Button", ChamferBox.make(fill, amber, geo("line_active"), c6, bm))
	var hov := ChamferBox.make(hover_fill, color("amber-300"), geo("line_active"), c6, bm)
	hov.glow = Color(amber, 0.35)
	t.set_stylebox("hover", "Button", hov)
	t.set_stylebox("pressed", "Button", ChamferBox.make(color("amber-700"), color("amber-300"), geo("line_active"), c6, bm))
	t.set_stylebox("hover_pressed", "Button", ChamferBox.make(color("amber-700"), color("amber-300"), geo("line_active"), c6, bm))
	t.set_stylebox("disabled", "Button", ChamferBox.make(color("ink-800"), color("steel-500"), geo("line_inactive"), c6, bm))
	t.set_stylebox("focus", "Button", ChamferBox.make(Color(0, 0, 0, 0), color("amber-300"), geo("line_inactive"), c6, Vector4.ZERO))
	t.set_font("font", "Button", font("label", body))
	t.set_font_size("font_size", "Button", body)
	t.set_color("font_color", "Button", amber)
	t.set_color("font_hover_color", "Button", color("amber-300"))
	t.set_color("font_focus_color", "Button", amber)
	t.set_color("font_pressed_color", "Button", color("white"))
	t.set_color("font_hover_pressed_color", "Button", color("white"))
	t.set_color("font_disabled_color", "Button", color("steel-500"))
	t.set_constant("h_separation", "Button", 8)

	# secondary button: steel-300 frame and text; hover white text
	t.set_type_variation("SecondaryButton", "Button")
	t.set_stylebox("normal", "SecondaryButton", ChamferBox.make(fill, dim, geo("line_inactive"), c6, bm))
	t.set_stylebox("hover", "SecondaryButton", ChamferBox.make(color("ink-600"), text, geo("line_inactive"), c6, bm))
	t.set_stylebox("pressed", "SecondaryButton", ChamferBox.make(color("ink-600"), color("white"), geo("line_inactive"), c6, bm))
	t.set_stylebox("hover_pressed", "SecondaryButton", ChamferBox.make(color("ink-600"), color("white"), geo("line_inactive"), c6, bm))
	t.set_color("font_color", "SecondaryButton", dim)
	t.set_color("font_hover_color", "SecondaryButton", color("white"))
	t.set_color("font_focus_color", "SecondaryButton", dim)
	t.set_color("font_pressed_color", "SecondaryButton", color("white"))
	t.set_color("font_hover_pressed_color", "SecondaryButton", color("white"))

	# main-menu item (5.1): Chakra Petch 28 caps on no frame; hover/focus = amber bar + glow + 4 px indent
	t.set_type_variation("MainMenuItem", "Button")
	var mpad := Vector4(geo("gutter"), 6, geo("gutter"), 6)
	var mnorm := ChamferBox.make(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 0, mpad)
	var msel := ChamferBox.make(Color(amber, 0.10), Color(0, 0, 0, 0), 0, 0,
		Vector4(mpad.x + geo("menu_indent"), mpad.y, mpad.z, mpad.w))
	msel.left_bar = geo("menu_bar")
	msel.left_bar_colour = amber
	msel.glow = Color(amber, 0.25)
	t.set_stylebox("normal", "MainMenuItem", mnorm)
	t.set_stylebox("disabled", "MainMenuItem", mnorm)
	t.set_stylebox("hover", "MainMenuItem", msel)
	t.set_stylebox("pressed", "MainMenuItem", msel)
	t.set_stylebox("hover_pressed", "MainMenuItem", msel)
	t.set_stylebox("focus", "MainMenuItem", msel)
	t.set_font("font", "MainMenuItem", font("display", size("menu_item")))
	t.set_font_size("font_size", "MainMenuItem", size("menu_item"))
	t.set_color("font_color", "MainMenuItem", text)
	t.set_color("font_hover_color", "MainMenuItem", amber)
	t.set_color("font_focus_color", "MainMenuItem", amber)
	t.set_color("font_pressed_color", "MainMenuItem", color("amber-300"))
	t.set_color("font_hover_pressed_color", "MainMenuItem", color("amber-300"))
	t.set_color("font_disabled_color", "MainMenuItem", color("steel-500"))

	# tabs: underline style, 3 px amber bar under the active one, caps
	var tab_sel := StyleBoxFlat.new()
	tab_sel.bg_color = Color(0, 0, 0, 0)
	tab_sel.border_color = amber
	tab_sel.border_width_bottom = int(geo("tab_bar"))
	tab_sel.set_content_margin_all(8)
	var tab_off := StyleBoxEmpty.new()
	tab_off.set_content_margin_all(8)
	for tt in ["TabBar", "TabContainer"]:
		t.set_stylebox("tab_selected", tt, tab_sel)
		t.set_stylebox("tab_unselected", tt, tab_off)
		t.set_stylebox("tab_hovered", tt, tab_off)
		t.set_font("font", tt, font("label", lab))
		t.set_color("font_selected_color", tt, amber)
		t.set_color("font_unselected_color", tt, dim)
		t.set_color("font_hovered_color", tt, color("white"))
	t.set_stylebox("panel", "TabContainer", StyleBoxEmpty.new())

	# bars and sliders: 6 px ink-600 track, accent fill
	t.set_stylebox("background", "ProgressBar", _flat(color("ink-600")))
	t.set_stylebox("fill", "ProgressBar", _flat(amber))
	t.set_font("font", "ProgressBar", font("numeric"))
	t.set_color("font_color", "ProgressBar", text)
	var track := _flat(color("ink-600"))
	track.content_margin_top = geo("slider_track") * 0.5
	track.content_margin_bottom = geo("slider_track") * 0.5
	t.set_stylebox("slider", "HSlider", track)
	t.set_stylebox("grabber_area", "HSlider", _flat(amber))
	t.set_stylebox("grabber_area_highlight", "HSlider", _flat(color("amber-300")))

	# scrollbars, separators
	t.set_stylebox("scroll", "VScrollBar", _flat(color("ink-800")))
	t.set_stylebox("grabber", "VScrollBar", _flat(color("steel-500")))
	t.set_stylebox("grabber_highlight", "VScrollBar", _flat(color("amber-700")))
	t.set_stylebox("grabber_pressed", "VScrollBar", _flat(amber))
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	var rule := StyleBoxLine.new()
	rule.color = color("steel-500")
	rule.thickness = 1
	t.set_stylebox("separator", "HSeparator", rule)

	# tooltips: ink-900 at 95 %, 1 px steel-500, 8 px padding
	var tip := ChamferBox.make(color("ink-900", alpha("tooltip-fill")), color("steel-500"), 1, 0,
		Vector4(geo("tooltip_padding"), geo("tooltip_padding"), geo("tooltip_padding"), geo("tooltip_padding")))
	t.set_stylebox("panel", "TooltipPanel", tip)
	t.set_color("font_color", "TooltipLabel", text)
	t.set_font("font", "TooltipLabel", font("body"))
	_theme = t
	return t


static func _label_type(t: Theme, name: String, f: Font, px: int, col: Color) -> void:
	t.set_type_variation(name, "Label")
	t.set_font("font", name, f)
	t.set_font_size("font_size", name, px)
	t.set_color("font_color", name, col)
	t.set_constant("line_spacing", name, 0)


static func _flat(c: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = c
	return s


## A label of a role's look; caps follow the role's token ("display" and "label" are ALL CAPS).
static func label(text: String, variation := "", col := Color(0, 0, 0, 0)) -> Label:
	var l := Label.new()
	l.theme_type_variation = variation
	var role: String = {"TitleLabel": "display", "BannerLabel": "display", "SectionLabel": "display", "SubheadLabel": "display",
		"CapsLabel": "label"}.get(variation, "body")
	l.text = text.to_upper() if caps(role) else text
	if col.a > 0.0:
		l.add_theme_color_override("font_color", col)
	return l


# ------------------------------------------------------------------------------- motion

## Panel in (4.4): an 8 px slide and a fade over 180 ms, ease-out; delay staggers a sequence.
## Skipped under "reduce motion".
static func panel_in(c: Control, delay := 0.0, from := Vector2(0, 1)) -> void:
	if reduce_motion() or not c.is_inside_tree():
		return
	var end := c.position
	c.position = end + from * data().get("motion", {}).get("panel_slide_px", 8)
	c.modulate.a = 0.0
	var tw := c.create_tween().set_parallel(true).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	tw.tween_property(c, "position", end, motion_s("slow")).set_delay(delay)
	tw.tween_property(c, "modulate:a", 1.0, motion_s("slow")).set_delay(delay)


## A plain fade-in over 180 ms (for a control a Container re-lays out, where a slide would fight the layout).
static func fade_in(c: Control) -> void:
	if reduce_motion() or not c.is_inside_tree():
		return
	c.modulate.a = 0.0
	c.create_tween().tween_property(c, "modulate:a", 1.0, motion_s("slow")).set_ease(Tween.EASE_OUT)


## Screen-entry boot flicker (4.4): a few frames of alpha stutter, then on. Skipped under reduce motion.
static func boot_flicker(c: Control) -> void:
	if reduce_motion() or not c.is_inside_tree():
		return
	var tw := c.create_tween()
	var frame := 1.0 / 30.0
	for a in [0.0, 0.7, 0.2, 1.0]:
		tw.tween_property(c, "modulate:a", a, 0.0)
		tw.tween_interval(frame)


## A number counting up to its value (debrief, 800 ms ease-out); fmt takes one int.
static func count_up(l: Label, value: int, fmt := "%d", delay := 0.0) -> void:
	if reduce_motion() or not l.is_inside_tree():
		l.text = fmt % value
		return
	l.text = fmt % 0
	var tw := l.create_tween()
	tw.tween_interval(delay)
	tw.tween_method(func(v: float): l.text = fmt % roundi(v), 0.0, float(value), motion_s("count_up")) \
		.set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)


# ------------------------------------------------------------------------------- stylebox

## A chamfered thin-line frame (4.1): 45-degree cuts on all four corners, 1 or 2 px border,
## optional faint diagonal hatch, a 1 px top-edge highlight, corner-tick brackets, a left
## selection bar and an outer glow line. Corner radius 0, no shadows.
class ChamferBox:
	extends StyleBox

	var fill := Color(0, 0, 0, 0)
	var edge := Color(0, 0, 0, 0)
	var width := 1.0
	var cut := 10.0
	var hatch := false
	var bracket := 0.0  # corner-tick length; 0 = none
	var bracket_colour := Color.WHITE
	var left_bar := 0.0  # selected-row bar width; 0 = none
	var left_bar_colour := Color.WHITE
	var glow := Color(0, 0, 0, 0)  # an outer line 2 px out; alpha 0 = none

	static func make(fill_c: Color, edge_c: Color, w: float, c: float, pad := Vector4.ZERO, hatched := false) -> ChamferBox:
		var b := ChamferBox.new()
		b.fill = fill_c
		b.edge = edge_c
		b.width = w
		b.cut = c
		b.hatch = hatched
		b.content_margin_left = pad.x
		b.content_margin_top = pad.y
		b.content_margin_right = pad.z
		b.content_margin_bottom = pad.w
		return b

	static func outline(r: Rect2, c: float) -> PackedVector2Array:
		var p := r.position
		var w := r.size.x
		var h := r.size.y
		c = minf(c, minf(w, h) * 0.5)
		if c <= 0.0:
			return PackedVector2Array([p, p + Vector2(w, 0), p + Vector2(w, h), p + Vector2(0, h)])
		return PackedVector2Array([p + Vector2(c, 0), p + Vector2(w - c, 0), p + Vector2(w, c), p + Vector2(w, h - c),
			p + Vector2(w - c, h), p + Vector2(c, h), p + Vector2(0, h - c), p + Vector2(0, c)])

	func _draw(ci: RID, rect: Rect2) -> void:
		if rect.size.x < 1.0 or rect.size.y < 1.0:
			return
		var poly := outline(rect, cut)
		if glow.a > 0.0:
			var g := outline(rect.grow(2.0), cut + 1.0)
			g.append(g[0])
			RenderingServer.canvas_item_add_polyline(ci, g, PackedColorArray([glow]), 1.0)
		if fill.a > 0.0:
			RenderingServer.canvas_item_add_polygon(ci, poly, PackedColorArray([fill]))
		if hatch:
			var hc := Color(1, 1, 1, StyleTokens.alpha("hatch"))
			var step := 8.0
			var x := -rect.size.y
			while x < rect.size.x:
				var seg := PackedVector2Array([rect.position + Vector2(x, rect.size.y), rect.position + Vector2(x + rect.size.y, 0)])
				for piece in Geometry2D.intersect_polyline_with_polygon(seg, poly):
					RenderingServer.canvas_item_add_polyline(ci, piece, PackedColorArray([hc]), 1.0)
				x += step
			# one-step top-edge highlight
			var c := minf(cut, minf(rect.size.x, rect.size.y) * 0.5)
			RenderingServer.canvas_item_add_line(ci, rect.position + Vector2(c, 1.5), rect.position + Vector2(rect.size.x - c, 1.5),
				Color(1, 1, 1, 0.06), 1.0)
		if left_bar > 0.0:
			RenderingServer.canvas_item_add_rect(ci, Rect2(rect.position, Vector2(left_bar, rect.size.y)), left_bar_colour)
		if width > 0.0 and edge.a > 0.0:
			var o := poly.duplicate()
			o.append(o[0])
			# inset by half the width so a 2 px line stays inside the rect
			if width > 1.0:
				o = outline(rect.grow(-width * 0.5), cut)
				o.append(o[0])
			RenderingServer.canvas_item_add_polyline(ci, o, PackedColorArray([edge]), width)
		if bracket > 0.0:
			var p := rect.position
			var w := rect.size.x
			var h := rect.size.y
			var a := minf(bracket, minf(w, h) * 0.4)
			var i := 3.0
			var bc := PackedColorArray([bracket_colour])
			for corner in [[Vector2(i, i), 1, 1], [Vector2(w - i, i), -1, 1], [Vector2(i, h - i), 1, -1], [Vector2(w - i, h - i), -1, -1]]:
				var at: Vector2 = p + corner[0]
				RenderingServer.canvas_item_add_polyline(ci, PackedVector2Array([at + Vector2(0, a * corner[2]), at,
					at + Vector2(a * corner[1], 0)]), bc, 2.0)
