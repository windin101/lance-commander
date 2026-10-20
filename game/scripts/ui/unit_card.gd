class_name UnitCard
extends PanelContainer
## Lance-panel card for one player unit (the original's force group bar, restyled to the
## approved HUD mock-up). Compact by default: group number, callsign, 'Mech, a small paper
## doll, armour and heat bars. Expanded (the selected unit): portrait, callsign, 'Mech /
## variant / tonnage, main weapons with ammo, armour and heat bars, and RUN / JUMP / GUARD /
## STOP buttons. A yellow blinking outline marks the pilot who is talking (comms).
## Left-click selects (shift adds), double-click centres the camera on the unit.

signal picked(unit: SimUnit, add: bool)
signal ordered(unit: SimUnit, kind: String)
signal focus_requested(unit: SimUnit)

const ACTIONS := [["run", "Run"], ["jump", "Jump"], ["guard", "Guard"], ["stop", "Stop"]]
const BLINK_PERIOD := 0.25  # the mock-up's 0.25 s steps(2) blink

var unit: SimUnit
var kit: HudKit
var force_index := 1  # position in the force
var group := 1:  # the number on the card
	set(v):
		if v != group:
			group = v
			if _gid_label:
				_gid_label.text = str(v)
var _gid_label: Label
var selected := false:
	set(v):
		if v != selected:
			selected = v
			_restyle()
var expanded := false:
	set(v):
		if v != expanded:
			expanded = v
			_build()
var speaking := false
var active_mode := ""  # the armed order button to light (MissionHud.command_mode)
var hover_help: Callable  # (title, text) -> void, the rollover help line
var doll: DollView
var armor_bar: HudKit.Bar
var heat_bar: HudKit.Bar
var armor_pct: Label
var heat_pct: Label
var sub_label: Label
var buttons := {}  # action -> Button
var _ammo_labels: Array = []  # [Label, inventory indices]


func _init(u: SimUnit, hud_kit: HudKit = null, number := 1) -> void:
	unit = u
	kit = hud_kit if hud_kit else HudKit.new(UiStyle.hud_unit(1080.0))
	group = number
	force_index = number
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = ""
	_restyle()
	_build()


func _restyle() -> void:
	if kit == null:
		return
	var s := StyleBoxFlat.new()
	s.bg_color = UiStyle.HUD_PANEL_2 if not selected else UiStyle.HUD_PANEL_2.lerp(UiStyle.HUD_EDGE, 0.12)
	s.border_color = UiStyle.HUD_EDGE if selected else Color(UiStyle.HUD_EDGE, 0.22)
	s.set_border_width_all(1)
	if selected:
		s.shadow_color = Color(UiStyle.HUD_GLOW, 0.35)
		s.shadow_size = roundi(kit.em(0.5))
	var pad := kit.em(0.55) if expanded else kit.em(0.35)
	s.content_margin_left = pad
	s.content_margin_right = pad
	s.content_margin_top = pad
	s.content_margin_bottom = pad
	add_theme_stylebox_override("panel", s)


func _build() -> void:
	for c in get_children():
		remove_child(c)
		c.queue_free()
	buttons.clear()
	_ammo_labels.clear()
	_restyle()
	if expanded:
		_build_full()
	else:
		_build_compact()
	_refresh()


func _gid() -> PanelContainer:
	var tag := PanelContainer.new()
	var s := StyleBoxFlat.new()
	s.bg_color = UiStyle.HUD_EDGE
	s.content_margin_left = kit.em(0.35)
	s.content_margin_right = kit.em(0.35)
	tag.add_theme_stylebox_override("panel", s)
	tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_gid_label = kit.label(str(group), "display700", 0.9, Color(0.012, 0.063, 0.09))
	tag.add_child(_gid_label)
	return tag


func _subtitle() -> String:
	var bits: Array[String] = [unit.name]
	if expanded and unit is SimMech and not String(unit.variant_name).is_empty() and unit.variant_name != unit.name:
		bits.append(String(unit.variant_name).replace(unit.name, "").strip_edges() if String(unit.variant_name).begins_with(unit.name) else unit.variant_name)
	if expanded and unit.tonnage > 0.0:
		bits.append("%d t" % roundi(unit.tonnage))
	return " · ".join(bits)


func callsign() -> String:
	return unit.pilot.name if unit.pilot and not unit.pilot.name.is_empty() else unit.name


func _build_compact() -> void:
	var h := kit.hbox(0.55)
	add_child(h)
	var g := _gid()
	g.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(g)
	var names := VBoxContainer.new()
	names.add_theme_constant_override("separation", 0)
	names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	names.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(names)
	var n := kit.label(callsign(), "display600", 1.05, UiStyle.HUD_INK, true, 0.05)
	n.clip_text = true
	names.add_child(n)
	sub_label = kit.label(_subtitle(), "body500", 0.9, UiStyle.HUD_DIM)
	sub_label.clip_text = true
	names.add_child(sub_label)
	doll = DollView.new(unit)
	doll.custom_minimum_size = Vector2(kit.em(2.4), kit.em(2.6))
	h.add_child(doll)
	h.add_child(_bars(7.5, true))


func _build_full() -> void:
	var v := kit.vbox(0.4)
	add_child(v)
	var top := kit.hbox(0.7)
	v.add_child(top)
	# portrait with the group number on its corner
	var face := Control.new()
	face.custom_minimum_size = Vector2(kit.em(4.6), kit.em(4.6) * 46.0 / 33.0)
	face.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(face)
	var portrait := TextureRect.new()
	portrait.name = "Portrait"
	portrait.texture = PilotPortraits.texture_for(unit.pilot_profile)
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	portrait.set_anchors_preset(Control.PRESET_FULL_RECT)
	portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	face.add_child(portrait)
	var frame := Panel.new()
	var fs := StyleBoxFlat.new()
	fs.draw_center = false
	fs.border_color = UiStyle.HUD_EDGE_SOFT
	fs.set_border_width_all(1)
	frame.add_theme_stylebox_override("panel", fs)
	frame.set_anchors_preset(Control.PRESET_FULL_RECT)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	face.add_child(frame)
	face.add_child(_gid())
	# callsign, chassis line, main weapons
	var mid := kit.vbox(0.3)
	mid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(mid)
	var names := VBoxContainer.new()
	names.add_theme_constant_override("separation", 0)
	names.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mid.add_child(names)
	names.add_child(kit.label(callsign(), "display600", 1.12, UiStyle.HUD_INK, true, 0.05))
	sub_label = kit.label(_subtitle(), "body500", 0.96, UiStyle.HUD_DIM)
	sub_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	sub_label.custom_minimum_size.x = kit.em(10.0)
	names.add_child(sub_label)
	var wl := VBoxContainer.new()
	wl.add_theme_constant_override("separation", roundi(kit.em(0.1)))
	wl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mid.add_child(wl)
	for grp in SystemsMonitor.weapon_groups(unit).slice(0, 3):
		var row := kit.hbox(0.6)
		var nm := kit.label(grp["label"], "body400", 0.98, UiStyle.HUD_INK)
		nm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		nm.clip_text = true
		row.add_child(nm)
		var am := kit.label("", "mono", 0.98, UiStyle.HUD_DIM)
		row.add_child(am)
		_ammo_labels.append([am, grp["items"]])
		wl.add_child(row)
	doll = DollView.new(unit)
	doll.custom_minimum_size = Vector2(kit.em(3.6), kit.em(4.8))
	doll.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	top.add_child(doll)
	v.add_child(_bars(0.0, false))
	var acts := GridContainer.new()
	acts.columns = 4
	acts.add_theme_constant_override("h_separation", roundi(kit.em(0.3)))
	for a in ACTIONS:
		var b := Button.new()
		b.text = a[1].to_upper()
		b.focus_mode = Control.FOCUS_NONE
		b.toggle_mode = a[0] != "stop"
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(func(): ordered.emit(unit, a[0]))
		b.mouse_entered.connect(func(): if hover_help.is_valid(): hover_help.call(a[0]))
		b.mouse_exited.connect(func(): if hover_help.is_valid(): hover_help.call(""))
		acts.add_child(b)
		buttons[a[0]] = b
	v.add_child(acts)


## ARMOR / HEAT rows: label, bar, percentage (the mock-up's .bars grid).
func _bars(width_em: float, compact: bool) -> GridContainer:
	var g := GridContainer.new()
	g.columns = 3
	g.add_theme_constant_override("h_separation", roundi(kit.em(0.4)))
	g.add_theme_constant_override("v_separation", roundi(kit.em(0.15 if compact else 0.25)))
	g.mouse_filter = Control.MOUSE_FILTER_IGNORE
	g.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if width_em > 0.0:
		g.custom_minimum_size.x = kit.em(width_em)
	var fs := 0.8 if compact else 0.85
	for row in [["ARMOR" if not compact else "AR", "ok"], ["HEAT" if not compact else "HT", "heat"]]:
		var l := kit.label(row[0], "mono", fs, UiStyle.HUD_DIM)
		l.custom_minimum_size.x = kit.em(1.6 if compact else 3.0)
		g.add_child(l)
		var b := kit.bar(0.4 if compact else 0.45, row[1])
		g.add_child(b)
		var p := kit.label("", "mono", fs, UiStyle.HUD_DIM)
		p.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		p.custom_minimum_size.x = kit.em(2.3)
		g.add_child(p)
		if row[1] == "ok":
			armor_bar = b
			armor_pct = p
		else:
			heat_bar = b
			heat_pct = p
	return g


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if event.double_click:
			focus_requested.emit(unit)
		else:
			picked.emit(unit, event.shift_pressed)
		accept_event()


func _process(_delta: float) -> void:
	_refresh()
	if speaking:
		queue_redraw()


func _refresh() -> void:
	if armor_bar == null:
		return
	var a := PaperDoll.armor_fraction(unit)
	armor_bar.value = a
	armor_pct.text = "%d%%" % roundi(a * 100.0)
	var heat := unit.heat / maxf(unit.heat_capacity, 0.01) if unit.uses_heat else 0.0
	heat_bar.value = heat
	heat_pct.text = "%d%%" % roundi(heat * 100.0) if unit.uses_heat else "—"
	var st := status_text(unit)
	if sub_label:
		sub_label.text = _subtitle() if st.is_empty() else st
		sub_label.add_theme_color_override("font_color", UiStyle.HUD_DIM if st.is_empty() else UiStyle.HUD_WARN)
	for al in _ammo_labels:
		var shots := 0
		var unlimited := false
		for inv in al[1]:
			var s := unit.weapon_shots(inv)
			if s < 0:
				unlimited = true
			else:
				shots = s  # one ammo pool per type
		al[0].text = "—" if unlimited else str(shots)
	for k in buttons:
		var b: Button = buttons[k]
		if b.toggle_mode:
			b.set_pressed_no_signal(active_mode == k)


## Status word for a unit that is not simply fighting, or "" when it is.
static func status_text(u: SimUnit) -> String:
	if u.status == SimUnit.Status.DESTROYED:
		return "DESTROYED"
	if u.status == SimUnit.Status.DISABLED:
		return "DISABLED"
	if u.powered_down:
		return "POWERED DOWN"
	if u.status == SimUnit.Status.SHUTDOWN:
		return "SHUTDOWN"
	if u is SimMech and u.fallen:
		return "FALLEN"
	if u.ignore_heat_discipline:
		return "ALPHA STRIKE"
	return ""


func _draw() -> void:
	if speaking and int(Time.get_ticks_msec() / (BLINK_PERIOD * 500.0)) % 2 == 0:
		draw_rect(Rect2(Vector2.ONE, size - Vector2(2, 2)), UiStyle.HUD_WARN, false, 2.0)
