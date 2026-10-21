class_name BayKit
extends HudKit
## Builders shared by the Mech Bay and the Mech Lab (issue I86 mock-up), on top of the HUD
## kit: the hangar backdrop, panels placed by viewport fractions, hardpoint badges, status
## chips, stat and slot bars, the primary button style.

# Hardpoint colours of the mock-up (.hp.B / .E / .M / .X).
const HP_COLOURS := {"B": Color("#e0a04a"), "E": Color("#4fb8ff"), "M": Color("#ff6f5a"), "X": Color("#9aa9b3")}
const DARK_TEXT := Color("#061016")


func _init(unit_px: float) -> void:
	super(unit_px)


## Pin c to fractions of its parent (left, top, right, bottom anchors). width_em > 0 makes
## it that wide from the left anchor (or from the right one when right_side).
func place(c: Control, l: float, t: float, r: float, b: float, width_em := 0.0, right_side := false) -> Control:
	c.anchor_left = l
	c.anchor_top = t
	c.anchor_right = r
	c.anchor_bottom = b
	c.offset_left = 0
	c.offset_top = 0
	c.offset_right = 0
	c.offset_bottom = 0
	if width_em > 0.0:
		if right_side:
			c.anchor_left = r
			c.offset_left = -em(width_em)
		else:
			c.anchor_right = l
			c.offset_right = em(width_em)
	return c


func primary(b: Button) -> Button:
	for state in ["normal", "hover", "pressed"]:
		var s := StyleBoxFlat.new()
		s.bg_color = Color(UiStyle.HUD_EDGE, 0.28 if state == "normal" else 0.4)
		s.border_color = UiStyle.HUD_EDGE
		s.set_border_width_all(1)
		s.shadow_color = Color(UiStyle.HUD_GLOW, 0.5)
		s.shadow_size = px(0.6)
		s.content_margin_left = em(0.9)
		s.content_margin_right = em(0.9)
		s.content_margin_top = em(0.45)
		s.content_margin_bottom = em(0.45)
		b.add_theme_stylebox_override(state, s)
	return b


func button(text: String, on_press: Callable, is_primary := false) -> Button:
	var b := Button.new()
	b.text = text.to_upper()
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_constant_override("outline_size", 0)
	if is_primary:
		primary(b)
	b.pressed.connect(on_press)
	return b


## A hardpoint badge (.hp): type letter on its colour, or outlined when free.
func badge(type: String, free := false, text := "") -> PanelContainer:
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var s := StyleBoxFlat.new()
	var c: Color = HP_COLOURS.get(type, HP_COLOURS["X"])
	s.bg_color = Color(0, 0, 0, 0) if free else c
	s.border_color = c
	s.set_border_width_all(1 if free else 0)
	s.set_corner_radius_all(2)
	s.content_margin_left = em(0.3)
	s.content_margin_right = em(0.3)
	p.add_theme_stylebox_override("panel", s)
	var l := label(text if text != "" else ("EQ" if type == "X" else type), "display700", 0.8, c if free else DARK_TEXT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.custom_minimum_size = Vector2(em(1.0), em(1.15))
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	p.add_child(l)
	return p


## A status chip (.chip): caps text in an outline of its colour.
func chip(text: String, colour: Color) -> PanelContainer:
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var s := StyleBoxFlat.new()
	s.bg_color = Color(0, 0, 0, 0)
	s.border_color = colour
	s.set_border_width_all(1)
	s.content_margin_left = em(0.5)
	s.content_margin_right = em(0.5)
	s.content_margin_top = em(0.1)
	s.content_margin_bottom = em(0.1)
	p.add_theme_stylebox_override("panel", s)
	p.add_child(label(text, "display600", 0.78, colour, true, 0.12))
	p.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	return p


## A coloured range square (.rng).
func range_mark(range_name: String) -> ColorRect:
	var r := ColorRect.new()
	r.color = UiStyle.RANGE_COLOURS.get(range_name, Color(0, 0, 0, 0))
	r.custom_minimum_size = Vector2(em(0.7), em(0.7))
	r.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## A top-bar figure (.fig): small caps title, mono value, optional bar under it.
func fig(title: String, with_bar := false) -> Dictionary:
	var v := vbox(0.2)
	v.custom_minimum_size.x = em(11)
	v.add_child(label(title, "display600", 0.78, UiStyle.HUD_DIM, true, 0.14))
	var val := label("", "mono", 1.35, UiStyle.HUD_EDGE)
	v.add_child(val)
	var b: StatBar = null
	if with_bar:
		b = StatBar.new()
		b.custom_minimum_size = Vector2(0, maxf(2.0, roundf(em(0.45))))
		v.add_child(b)
	return {"box": v, "value": val, "bar": b}


static func money(v: int) -> String:
	var s := str(absi(v))
	var out := ""
	while s.length() > 3:
		out = "," + s.right(3) + out
		s = s.left(s.length() - 3)
	return ("-" if v < 0 else "") + s + out


## The mission's player paint (its first home-commander part), [red, green, blue] ARGB.
static func player_paint(mission: String) -> Array:
	var path := "res://data/missions/%s.json" % mission
	if FileAccess.file_exists(path):
		var fit = JSON.parse_string(FileAccess.get_file_as_string(path))
		if fit is Dictionary:
			for i in range(1, int(fit.get("Parts", {}).get("NumParts", 0)) + 1):
				var part: Dictionary = fit.get("Part%d" % i, {})
				if int(part.get("CommanderID", -1)) == 0:
					return [int(part.get("HighlightColor1", -1)), int(part.get("HighlightColor2", -1)), int(part.get("BaseColor", -1))]
	return [-4144960, -8355712, -16744256]


## A gauge (.bar): track, fill (cyan, or a colour; the heat gradient; red when over) and a
## pale ghost line for the stock value.
class StatBar:
	extends Control
	var value := 0.0:
		set(v):
			value = v
			queue_redraw()
	var ghost := -1.0:
		set(v):
			ghost = v
			queue_redraw()
	var colour := UiStyle.HUD_EDGE
	var heat := false
	var over := false

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		size_flags_horizontal = Control.SIZE_EXPAND_FILL
		size_flags_vertical = Control.SIZE_SHRINK_CENTER

	func _draw() -> void:
		draw_rect(Rect2(Vector2.ZERO, size), Color(1, 1, 1, 0.08))
		var f := clampf(value, 0.0, 1.0)
		var w := size.x * f
		if w > 0.0:
			if over:
				draw_rect(Rect2(0, 0, w, size.y), UiStyle.HUD_CRIT)
			elif heat:
				var c1 := UiStyle.HUD_HOT
				draw_polygon(PackedVector2Array([Vector2.ZERO, Vector2(w, 0), Vector2(w, size.y), Vector2(0, size.y)]),
					PackedColorArray([UiStyle.HUD_WARN, c1, c1, UiStyle.HUD_WARN]))
			else:
				draw_rect(Rect2(0, 0, w, size.y), colour)
		if ghost >= 0.0:
			var x := roundf(size.x * clampf(ghost, 0.0, 1.0))
			draw_rect(Rect2(x - 1.0, -size.y * 0.45, 2.0, size.y * 1.9), Color(UiStyle.HUD_INK, 0.6))


## A location's slot strip (.slots): one segment per slot; fixed items grey, parts cyan,
## parts new in this refit amber.
class SlotBar:
	extends Control
	var cap := 12
	var fixed := 0
	var used := 0
	var fresh := 0  # of the used parts' slots, how many are new (drawn last)

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		size_flags_horizontal = Control.SIZE_EXPAND_FILL

	func _draw() -> void:
		if cap <= 0:
			return
		var gap := 1.0
		var seg := (size.x - gap * (cap - 1)) / cap
		for i in cap:
			var c := Color(1, 1, 1, 0.07)
			if i < fixed:
				c = Color(UiStyle.HUD_DIM, 0.35)
			elif i < used - fresh:
				c = UiStyle.HUD_EDGE
			elif i < used:
				c = UiStyle.HUD_WARN
			draw_rect(Rect2(i * (seg + gap), 0, seg, size.y), c)


## The hangar behind the screens: a dark gradient with a cyan glow in the middle, a
## perspective floor grid fading in toward the bottom, and two gantry columns.
class Backdrop:
	extends Control
	var gantries := true

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_preset(Control.PRESET_FULL_RECT)

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var top := Color("#101f2a")
		var mid := Color("#0e1b24")
		var bot := Color("#081117")
		draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h * 0.58), Vector2(0, h * 0.58)]),
			PackedColorArray([top, top, mid, mid]))
		draw_polygon(PackedVector2Array([Vector2(0, h * 0.58), Vector2(w, h * 0.58), Vector2(w, h), Vector2(0, h)]),
			PackedColorArray([mid, mid, bot, bot]))
		# glow: concentric ellipses, faint
		var c := Vector2(w * 0.5, h * 0.52)
		for i in 24:
			var k := 1.0 - float(i) / 24.0
			var pts := PackedVector2Array()
			for a in 49:
				var t := TAU * a / 48.0
				pts.append(c + Vector2(cos(t) * w * 0.3 * k, sin(t) * h * 0.3 * k))
			draw_colored_polygon(pts, Color(UiStyle.HUD_EDGE, 0.006))
		# floor grid: horizon at 66% of the height, lines converge to the centre
		var horizon := h * 0.64
		var grid := Color(UiStyle.HUD_EDGE, 0.16)
		for i in range(1, 15):
			var t := float(i) / 14.0
			var y := horizon + (h - horizon) * t * t
			draw_line(Vector2(0, y), Vector2(w, y), Color(grid, grid.a * clampf(t * 1.6, 0.0, 1.0)), 1.0)
		for i in range(-16, 17):
			var xb := w * 0.5 + i * w * 0.09
			var xt := w * 0.5 + i * w * 0.02
			draw_line(Vector2(xt, horizon + (h - horizon) * 0.02), Vector2(xb, h), Color(grid, 0.09), 1.0)
		if gantries:
			for gx in [w * 0.36, w * 0.64]:
				var gw := 16.0
				var y := 0.0
				var stripe := 0
				while y < h * 0.7:
					var col := Color(UiStyle.HUD_DIM, 0.10 if stripe % 2 == 0 else 0.03)
					draw_rect(Rect2(gx - gw * 0.5, y, gw, minf(14.0, h * 0.7 - y)), col)
					y += 14.0
					stripe += 1
				draw_line(Vector2(gx - gw * 0.5, 0), Vector2(gx - gw * 0.5, h * 0.7), Color(UiStyle.HUD_DIM, 0.12), 1.0)
				draw_line(Vector2(gx + gw * 0.5, 0), Vector2(gx + gw * 0.5, h * 0.7), Color(UiStyle.HUD_DIM, 0.12), 1.0)
