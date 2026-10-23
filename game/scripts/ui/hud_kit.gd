class_name HudKit
extends RefCounted
## Builders for the in-mission HUD at one base unit u (UiStyle.hud_unit): labels in the HUD
## fonts, framed panels with the mock-up's header strip, bars, vector icons and the heading
## tape. Every size is given in em (multiples of u), as in the approved mock-up's CSS.

var u := 11.4


func _init(unit_px: float) -> void:
	u = unit_px


func em(x: float) -> float:
	return x * u


func px(x: float) -> int:
	return maxi(1, roundi(x * u))


## A label: font role ("display600", "body400", "mono"...), size in em, colour, caps,
## letter spacing in em.
func label(text: String, kind := "body400", size_em := 1.0, colour := UiStyle.HUD_INK, caps := false, spacing_em := 0.0) -> Label:
	var l := Label.new()
	l.text = text
	l.uppercase = caps
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_override("font", UiStyle.font(kind, roundi(spacing_em * size_em * u)))
	l.add_theme_font_size_override("font_size", px(size_em))
	l.add_theme_color_override("font_color", colour)
	l.add_theme_constant_override("line_spacing", 0)
	return l


## A label that wraps inside width_em.
func para(text: String, width_em: float, kind := "body400", size_em := 1.1, colour := UiStyle.HUD_INK) -> Label:
	var l := label(text, kind, size_em, colour)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size.x = em(width_em)
	return l


## A framed panel (the mock-up's .p) with an optional header strip (.ph): title in the
## display face, a small mono note on the right, a soft rule under it. Returns
## {panel, body, title, small}; add content to body.
func panel(title := "", small := "", width_em := 0.0) -> Dictionary:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(u))
	p.mouse_filter = Control.MOUSE_FILTER_STOP
	if width_em > 0.0:
		p.custom_minimum_size.x = em(width_em)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 0)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(v)
	var out := {"panel": p, "body": v, "title": null, "small": null}
	if not title.is_empty():
		var m := margin(1.0, 0.55, 1.0, 0.45)
		v.add_child(m)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", px(1.0))
		m.add_child(h)
		var t := label(title, "display600", 1.05, UiStyle.HUD_EDGE, true, 0.12)
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		t.clip_text = true
		h.add_child(t)
		var s := label(small, "mono", 0.85 * 1.05, UiStyle.HUD_DIM, false, 0.04)
		s.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		s.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
		h.add_child(s)
		v.add_child(rule())
		out["title"] = t
		out["small"] = s
	return out


func margin(l: float, t: float, r: float, b: float) -> MarginContainer:
	var m := MarginContainer.new()
	m.mouse_filter = Control.MOUSE_FILTER_IGNORE
	m.add_theme_constant_override("margin_left", roundi(em(l)))
	m.add_theme_constant_override("margin_top", roundi(em(t)))
	m.add_theme_constant_override("margin_right", roundi(em(r)))
	m.add_theme_constant_override("margin_bottom", roundi(em(b)))
	return m


func rule(colour := UiStyle.HUD_EDGE_SOFT) -> ColorRect:
	var r := ColorRect.new()
	r.color = colour
	r.custom_minimum_size = Vector2(0, 1)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


func hbox(sep_em := 0.5) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", roundi(em(sep_em)))
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return h


func vbox(sep_em := 0.25) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", roundi(em(sep_em)))
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return v


func bar(height_em := 0.45, mode := "ok") -> Bar:
	var b := Bar.new()
	b.mode = mode
	b.custom_minimum_size = Vector2(0, maxf(2.0, roundf(em(height_em))))
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return b


## Health colour for a fraction (the mock-up legend): green, amber under 60%, red under 30%.
static func health_colour(frac: float) -> Color:
	if frac < 0.3:
		return UiStyle.HUD_CRIT
	if frac < 0.6:
		return UiStyle.HUD_WARN
	return UiStyle.HUD_OK


## A thin gauge (.bar): dim track and a fill. mode "ok" (health colour), "heat" (amber to
## orange gradient), "cool" / "edge" (cyan). mark >= 0 draws a red line there (heat shutdown).
class Bar:
	extends Control
	var value := 0.0:
		set(v):
			if not is_equal_approx(v, value):
				value = v
				queue_redraw()
	var mode := "ok"
	var colour := Color(0, 0, 0, 0)  # overrides the mode's colour when alpha > 0
	var mark := -1.0

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		draw_rect(Rect2(Vector2.ZERO, size), Color(1, 1, 1, 0.08))
		var f := clampf(value, 0.0, 1.0)
		var w := size.x * f
		if w > 0.0:
			if mode == "heat":
				var r := Rect2(Vector2.ZERO, Vector2(w, size.y))
				var c0 := UiStyle.HUD_WARN
				var c1 := UiStyle.HUD_WARN.lerp(UiStyle.HUD_HOT, f)
				draw_polygon(PackedVector2Array([r.position, Vector2(r.end.x, 0), r.end, Vector2(0, r.end.y)]),
					PackedColorArray([c0, c1, c1, c0]))
			else:
				var c := colour
				if c.a <= 0.0:
					c = HudKit.health_colour(f) if mode == "ok" else UiStyle.HUD_EDGE
				draw_rect(Rect2(0, 0, w, size.y), c)
		if mark >= 0.0:
			var x := roundf(size.x * clampf(mark, 0.0, 1.0))
			draw_rect(Rect2(x - 1.0, -size.y * 0.6, 2.0, size.y * 2.2), UiStyle.HUD_CRIT)


## The command icons of the mock-up, as polylines in a 24 x 24 box (its SVG paths).
const ICONS := {
	"run": [[Vector2(4, 12), Vector2(16, 12)], [Vector2(12, 6), Vector2(18, 12), Vector2(12, 18)]],
	"jump": ["c", Vector2(5, 18), Vector2(8, 10), Vector2(16, 10), Vector2(19, 18),
		[Vector2(12, 4), Vector2(12, 10)], [Vector2(9, 7), Vector2(12, 4), Vector2(15, 7)]],
	"guard": ["shield"],
	"stop": [[Vector2(8, 3), Vector2(16, 3), Vector2(21, 8), Vector2(21, 16), Vector2(16, 21), Vector2(8, 21),
		Vector2(3, 16), Vector2(3, 8), Vector2(8, 3)], [Vector2(9, 12), Vector2(15, 12)]],
	"fire_from_position": ["circle", [Vector2(12, 2), Vector2(12, 7)], [Vector2(12, 17), Vector2(12, 22)],
		[Vector2(2, 12), Vector2(7, 12)], [Vector2(17, 12), Vector2(22, 12)]],
	"hold": [[Vector2(6, 20), Vector2(6, 9)], [Vector2(10, 20), Vector2(10, 6)], [Vector2(14, 20), Vector2(14, 6)],
		[Vector2(18, 20), Vector2(18, 10)], [Vector2(4, 20), Vector2(20, 20)]],
	"alpha_strike": [[Vector2(13, 2), Vector2(5, 14), Vector2(11, 14), Vector2(10, 22), Vector2(18, 10), Vector2(12, 10), Vector2(13, 2)]],
	# range bands: one, two or three arcs ahead of a firing point
	"short": [[Vector2(4, 12), Vector2(7, 12)], "c", Vector2(10, 6), Vector2(13, 9), Vector2(13, 15), Vector2(10, 18)],
	"medium": [[Vector2(4, 12), Vector2(7, 12)], "c", Vector2(10, 6), Vector2(13, 9), Vector2(13, 15), Vector2(10, 18),
		"c", Vector2(14, 4), Vector2(18, 8), Vector2(18, 16), Vector2(14, 20)],
	"long": [[Vector2(4, 12), Vector2(7, 12)], "c", Vector2(10, 6), Vector2(13, 9), Vector2(13, 15), Vector2(10, 18),
		"c", Vector2(14, 4), Vector2(18, 8), Vector2(18, 16), Vector2(14, 20),
		"c", Vector2(18, 2), Vector2(23, 7), Vector2(23, 17), Vector2(18, 22)],
	# force fire: crosshair with a bar through it
	"force_fire": ["circle", [Vector2(12, 3), Vector2(12, 21)], [Vector2(3, 12), Vector2(21, 12)],
		[Vector2(5, 19), Vector2(19, 5)]],
	# lay mines: three mines on the ground line
	"lay_mines": [[Vector2(3, 18), Vector2(21, 18)], [Vector2(5, 18), Vector2(5, 15), Vector2(8, 15), Vector2(8, 18)],
		[Vector2(10, 18), Vector2(10, 15), Vector2(13, 15), Vector2(13, 18)],
		[Vector2(15, 18), Vector2(15, 15), Vector2(18, 15), Vector2(18, 18)], [Vector2(12, 4), Vector2(12, 11)],
		[Vector2(9, 8), Vector2(12, 11), Vector2(15, 8)]],
}


static func _cubic(a: Vector2, b: Vector2, c: Vector2, d: Vector2, n := 12) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in n + 1:
		var t := float(i) / n
		out.append(a.bezier_interpolate(b, c, d, t))
	return out


## Strokes for an icon id, in 24-box coordinates.
static func icon_strokes(id: String) -> Array:
	var out := []
	var items: Array = ICONS.get(id, [])
	var i := 0
	while i < items.size():
		var it = items[i]
		if it is String and it == "c":
			out.append(_cubic(items[i + 1], items[i + 2], items[i + 3], items[i + 4]))
			i += 5
			continue
		if it is String and it == "circle":
			var pts := PackedVector2Array()
			for k in 33:
				pts.append(Vector2(12, 12) + Vector2.from_angle(TAU * k / 32.0) * 6.0)
			out.append(pts)
		elif it is String and it == "shield":
			var s := PackedVector2Array([Vector2(12, 3), Vector2(19, 6), Vector2(19, 12)])
			s.append_array(_cubic(Vector2(19, 12), Vector2(19, 16), Vector2(16, 19), Vector2(12, 21)))
			s.append_array(_cubic(Vector2(12, 21), Vector2(8, 19), Vector2(5, 16), Vector2(5, 12)))
			s.append_array(PackedVector2Array([Vector2(5, 6), Vector2(12, 3)]))
			out.append(s)
		else:
			out.append(PackedVector2Array(it))
		i += 1
	return out


## Draw an icon into rect (a square) on a canvas item, stroke 1.6 of 24 as in the mock-up.
static func draw_icon(ci: CanvasItem, id: String, rect: Rect2, colour: Color) -> void:
	var k := rect.size.x / 24.0
	var w := maxf(1.0, 1.6 * k)
	for s in icon_strokes(id):
		var pts := PackedVector2Array()
		for p in s:
			pts.append(rect.position + p * k)
		ci.draw_polyline(pts, colour, w, true)


## Heading tape under the mission bar: ticks every 10 degrees, labels every 30 (N in cyan),
## and the camera heading in a box at the centre. heading is degrees clockwise from north.
class Tape:
	extends Control
	var heading := 0.0:
		set(v):
			if not is_equal_approx(v, heading):
				heading = v
				queue_redraw()
	var u := 11.4
	var span := 150.0  # degrees across the tape

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var f := UiStyle.font("mono")
		var fs := maxi(6, roundi(u * 0.9))
		draw_line(Vector2(0, 0), Vector2(size.x, 0), UiStyle.HUD_EDGE_SOFT, 1.0)
		var inner := size.x * 0.84  # the mock-up's 8% padding each side
		var x0 := size.x * 0.08
		var deg_px := inner / span
		var start := int(floor((heading - span / 2.0) / 10.0)) * 10
		for d in range(start, int(heading + span / 2.0) + 10, 10):
			var x := x0 + inner / 2.0 + (d - heading) * deg_px
			if x < x0 - 2.0 or x > x0 + inner + 2.0:
				continue
			var n := posmod(d, 360)
			if n % 30 == 0:
				var t := "N" if n == 0 else ("%03d" % n)
				var ts := f.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
				draw_string(f, Vector2(x - ts.x / 2.0, u * 0.25 + f.get_ascent(fs)), t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs,
					UiStyle.HUD_EDGE if n == 0 else UiStyle.HUD_DIM)
			else:
				draw_line(Vector2(x, 0), Vector2(x, u * 0.3), Color(UiStyle.HUD_DIM, 0.45), 1.0)
		var label := "%03d°" % posmod(roundi(heading), 360)
		var ls := f.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
		var box := Rect2(size.x / 2.0 - ls.x / 2.0 - u * 0.4, -u * 0.2, ls.x + u * 0.8, f.get_height(fs) + 2.0)
		draw_rect(box, UiStyle.HUD_PANEL_2)
		draw_rect(box, UiStyle.HUD_EDGE, false, 1.0)
		draw_string(f, Vector2(box.position.x + u * 0.4, box.position.y + 1.0 + f.get_ascent(fs)), label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, fs, UiStyle.HUD_INK)
