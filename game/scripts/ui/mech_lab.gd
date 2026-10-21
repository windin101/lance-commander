class_name MechLab
extends Control
## Mech Lab (issue I86; the approved mock-up, MechWarrior 5-style rules in Loadout): refit
## one inventory 'Mech.
##   left    parts: the mission's market plus stores, filtered All / Ballistic / Energy /
##           Missile / Equipment, with tons, slots, damage, heat and what you have
##   centre  the eight locations around the 'Mech's HD model: hardpoint badges, a slot strip,
##           fitted parts (x removes to stores); a selected part lights the locations that
##           can take it, and a click there fits it
##   right   stock -> new stats (tonnage, alpha, damage/sec, alpha heat vs capacity, armour,
##           speed, longest range), the reason line, the refit bill; Confirm / Revert / Save
## Confirm charges the parts bought and returns to the bay (refits are instant). Save
## variant names the loadout for its chassis so the bay can apply it to another 'Mech.
## Dev: --sample-campaign opens on mission 2's Bushwacker; --sample-edit also swaps its
## AC/10 for an AC/5 and a heat sink and selects a heat sink; --open=save opens Save variant.

const FILTERS := [["all", "All"], ["B", "Ballistic"], ["E", "Energy"], ["M", "Missile"], ["X", "Equipment"]]
# Location panels by column, as seen from the front: the 'Mech's right side on the left.
const COLUMNS := [["rarm", "rtorso", "rleg"], ["head", "ctorso"], ["larm", "ltorso", "lleg"]]

var mission := ""
var camp: Campaign
var kit: BayKit
var m: Dictionary
var chassis := ""
var vidx := 0
var entry: Dictionary  # the loadout's parts when the lab opened
var work: Dictionary  # the parts being edited
var sel := -1  # selected component id
var filter := "all"
var msg := {"t": "Pick a part on the left to see where it fits.", "k": ""}
var stage: MechStage
var _filters: HBoxContainer
var _plist: VBoxContainer
var _locs := {}  # loc -> PanelContainer
var _stats: VBoxContainer
var _vname: Label
var _sub: Label
var _ton_fig: Dictionary
var _cash_fig: Dictionary
var _confirm: Button
var _revert: Button
var _save: Button
var _overlay: Control


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mission = Flow.current
	camp = Flow.campaign
	var args := OS.get_cmdline_user_args()
	if args.has("--sample-campaign"):
		mission = MechBay.dev_sample(camp)
		Flow.current = mission
		Flow.lab_mech_id = int(camp.mechs[0]["id"])
	for c in camp.mechs:
		if int(c["id"]) == Flow.lab_mech_id:
			m = c
	if m.is_empty():
		Flow.goto_mech_bay.call_deferred()
		return
	chassis = String(m["chassis"])
	vidx = int(m["variant"])
	entry = Loadout.copy(camp.loadout(m)["parts"])
	work = Loadout.copy(entry)
	if args.has("--sample-edit"):
		work["larm"] = [100, 7]
		sel = 7
		msg = _pick_text(7)
	var vh := get_viewport().get_visible_rect().size.y if get_viewport() else 1080.0
	kit = BayKit.new(UiStyle.hud_unit(vh))
	theme = UiStyle.hud_theme(kit.u)
	_line_edit_theme(theme)
	var bg := ColorRect.new()
	bg.color = Color("#0b141b")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var back := BayKit.Backdrop.new()
	back.gantries = false
	add_child(back)
	_build()
	stage.show_mech(chassis, BayKit.player_paint(mission), -22.0)
	_refresh()
	if args.has("--open=save"):
		_open_save()


func _line_edit_theme(t: Theme) -> void:
	for state in ["normal", "focus"]:
		var s := StyleBoxFlat.new()
		s.bg_color = UiStyle.HUD_PANEL_2
		s.border_color = UiStyle.HUD_EDGE if state == "focus" else UiStyle.HUD_EDGE_SOFT
		s.set_border_width_all(1)
		s.content_margin_left = kit.em(0.6)
		s.content_margin_right = kit.em(0.6)
		s.content_margin_top = kit.em(0.35)
		s.content_margin_bottom = kit.em(0.35)
		t.set_stylebox(state, "LineEdit", s)
	t.set_font("font", "LineEdit", UiStyle.font("mono"))
	t.set_font_size("font_size", "LineEdit", kit.px(1.1))
	t.set_color("font_color", "LineEdit", UiStyle.HUD_INK)
	t.set_color("caret_color", "LineEdit", UiStyle.HUD_EDGE)


func _comp(id: int) -> Dictionary:
	return Loadout.component(GameData, id)


func _nm(id: int) -> String:
	return Loadout.short_name(String(_comp(id).get("name", "?")))


# --- layout ------------------------------------------------------------------------------

func _build() -> void:
	var top := PanelContainer.new()
	top.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	kit.place(top, 0.01, 0.016, 0.99, 0.016)
	add_child(top)
	var tm := kit.margin(1.4, 0.7, 1.4, 0.7)
	top.add_child(tm)
	var th := kit.hbox(2.4)
	tm.add_child(th)
	var title := kit.hbox(1.0)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.add_child(kit.label("Mech Lab", "display700", 1.5, UiStyle.HUD_INK, true, 0.14))
	var pilot := String(m["pilot"])
	var cname := String(GameData.chassis[chassis]["name"])
	_sub = kit.label("%s · %s" % [camp.pilots.get(pilot, {}).get("name", "Reserve") if pilot != "" else "Reserve", cname],
		"display500", 0.9, UiStyle.HUD_DIM, true, 0.1)
	_sub.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	title.add_child(_sub)
	_vname = kit.label("", "mono", 1.0, UiStyle.HUD_WARN, false, 0.04)
	_vname.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	title.add_child(_vname)
	th.add_child(title)
	_ton_fig = kit.fig("Tonnage", true)
	th.add_child(_ton_fig["box"])
	_cash_fig = kit.fig("C-Bills")
	th.add_child(_cash_fig["box"])
	var back := kit.button("Back to bay", func(): Flow.goto_mech_bay())
	back.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	th.add_child(back)

	# parts
	var parts := kit.panel("Parts", "mission market + stores")
	kit.place(parts["panel"], 0.01, 0.13, 0.01, 0.984, 30.0)
	add_child(parts["panel"])
	var fm := kit.margin(0.6, 0.6, 0.6, 0.3)
	parts["body"].add_child(fm)
	_filters = kit.hbox(0.35)
	fm.add_child(_filters)
	var hm := kit.margin(0.8, 0.3, 0.8, 0.3)
	parts["body"].add_child(hm)
	hm.add_child(_part_columns(["", "Part", "Tons", "Slot", "Dmg", "Heat", "Have"], true))
	parts["body"].add_child(kit.rule())
	var sc := ScrollContainer.new()
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	parts["body"].add_child(sc)
	var pm := kit.margin(0.4, 0.3, 0.4, 0.3)
	pm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sc.add_child(pm)
	_plist = kit.vbox(0.2)
	_plist.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pm.add_child(_plist)
	parts["body"].add_child(kit.rule())
	var nm := kit.margin(0.9, 0.6, 0.9, 0.6)
	parts["body"].add_child(nm)
	nm.add_child(kit.para("Pick a part, then a lit location. Parts in stores cost nothing to fit; the rest are bought at the market price. Removed parts go to stores.",
		27, "body400", 0.92, UiStyle.HUD_DIM))

	# locations around the 'Mech (the model sits behind them, below the head and torso rows)
	stage = MechStage.new()
	kit.place(stage, 0.33, 0.3, 0.745, 0.984)
	add_child(stage)
	var grid := kit.hbox(0.6)
	kit.place(grid, 0.33, 0.13, 0.745, 0.984)
	add_child(grid)
	for col in COLUMNS.size():
		var v := kit.vbox(0.6)
		v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		v.size_flags_stretch_ratio = 1.0
		v.mouse_filter = Control.MOUSE_FILTER_IGNORE
		grid.add_child(v)
		for loc in COLUMNS[col]:
			var p := PanelContainer.new()
			p.mouse_filter = Control.MOUSE_FILTER_STOP
			p.gui_input.connect(func(e):
				if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
					_install(loc))
			_locs[loc] = p
			v.add_child(p)

	# refit stats
	var st := kit.panel("Refit", "stock → new")
	kit.place(st["panel"], 0.99, 0.13, 0.99, 0.984, 23.5, true)
	add_child(st["panel"])
	var ss := ScrollContainer.new()
	ss.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	ss.size_flags_vertical = Control.SIZE_EXPAND_FILL
	st["body"].add_child(ss)
	var sm := kit.margin(0.9, 0.7, 0.9, 0.7)
	sm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ss.add_child(sm)
	_stats = kit.vbox(0.75)
	_stats.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sm.add_child(_stats)
	st["body"].add_child(kit.rule())
	var ff := kit.margin(0.6, 0.6, 0.6, 0.6)
	st["body"].add_child(ff)
	var fv := kit.vbox(0.5)
	ff.add_child(fv)
	_confirm = kit.button("Confirm refit", _do_confirm, true)
	fv.add_child(_confirm)
	var fh := GridContainer.new()
	fh.columns = 2
	fh.add_theme_constant_override("h_separation", kit.px(0.5))
	fv.add_child(fh)
	_revert = kit.button("Revert", func():
		work = Loadout.copy(entry)
		sel = -1
		msg = {"t": "Back to the loadout this 'Mech came in with.", "k": ""}
		_refresh())
	_revert.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fh.add_child(_revert)
	_save = kit.button("Save variant", _open_save)
	_save.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fh.add_child(_save)


## The parts table's columns (.phead / .row): badge, name, tons, slot, dmg, heat, have.
func _part_columns(cells: Array, header := false) -> HBoxContainer:
	var widths := [2.0, 0.0, 3.1, 2.4, 2.8, 2.6, 4.6]
	var h := kit.hbox(0.4)
	for i in cells.size():
		var c = cells[i]
		var node: Control
		if c is Control:
			node = c
		else:
			node = kit.label(String(c), "display600" if header else "mono", 0.72 if header else 0.88, UiStyle.HUD_DIM, header, 0.12 if header else 0.0)
			if i >= 2:
				(node as Label).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		if widths[i] > 0.0:
			node.custom_minimum_size.x = kit.em(widths[i])
		else:
			node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(node)
	return h


# --- state ---------------------------------------------------------------------------------

func _quote() -> Dictionary:
	return camp.refit_quote(m, work, mission)


func _have(q: Dictionary, id: int) -> int:
	return int(q["stores"].get(id, 0))


func _market() -> Dictionary:
	return camp.available_components(mission)


func _part_ids(q: Dictionary) -> Array:
	var market := _market()
	var ids := {}
	if market.has("all"):
		for id in GameData.components:
			var c := _comp(int(id))
			if Loadout.is_part(c) and int(c.get("rp", 0)) > 0:
				ids[int(id)] = true
	else:
		for id in market:
			if Loadout.is_part(_comp(int(id))):
				ids[int(id)] = true
	for id in q["stores"]:
		ids[int(id)] = true
	var order := {"B": 0, "E": 1, "M": 2, "X": 3}
	var out := ids.keys()
	out.sort_custom(func(a, b):
		var ka: int = order[Loadout.kind(_comp(a))]
		var kb: int = order[Loadout.kind(_comp(b))]
		if ka != kb:
			return ka < kb
		var ta := float(_comp(a).get("tons", 0.0))
		var tb := float(_comp(b).get("tons", 0.0))
		return ta > tb if ta != tb else a < b)
	return out


func _pick_text(id: int) -> Dictionary:
	var c := _comp(id)
	var k := Loadout.kind(c)
	return {"t": "%s: %s Lit locations can take it." % [String(c.get("name", "?")),
		"fits in any location with room." if k == "X" else "needs a %s hardpoint." % Loadout.TYPE_NAMES[k]], "k": ""}


func _install(loc: String) -> void:
	if sel < 0:
		return
	var why := Loadout.fits(GameData, chassis, vidx, work, sel, loc)
	if why == "":
		var trial := Loadout.copy(work)
		trial[loc].append(sel)
		var q := camp.refit_quote(m, trial, mission)
		if not q["unavailable"].is_empty():
			why = "%s is not on this mission's market." % String(_comp(sel).get("name", "?"))
		elif int(q["cost"]) > camp.c_bills:
			why = "Not enough C-Bills: this refit would cost %s." % BayKit.money(int(q["cost"]))
	if why != "":
		msg = {"t": why, "k": "bad"}
		_refresh()
		return
	var had := _have(_quote(), sel)
	work[loc].append(sel)
	msg = {"t": "%s fitted to the %s%s." % [String(_comp(sel).get("name", "?")), String(Loadout.LOC_NAMES[loc]).to_lower(),
		" from stores" if had > 0 else " (bought for %s C)" % BayKit.money(int(_comp(sel).get("rp", 0)))], "k": "good"}
	_refresh()


func _remove(loc: String, i: int) -> void:
	var id: int = work[loc][i]
	var bought_before := int(_quote()["bought"].get(id, 0))
	work[loc].remove_at(i)
	var bought_after := int(_quote()["bought"].get(id, 0))
	msg = {"t": ("%s removed; it was never paid for." if bought_after < bought_before else "%s moved to stores.") % String(_comp(id).get("name", "?")), "k": ""}
	_refresh()


func _do_confirm() -> void:
	var problem := camp.refit_problem(m, work, mission)
	if problem != "":
		msg = {"t": problem + ".", "k": "bad"}
		_refresh()
		return
	camp.refit(m, work, mission)
	Flow.save_progress()
	Flow.goto_mech_bay()


# --- refresh -------------------------------------------------------------------------------

func _refresh() -> void:
	var q := _quote()
	_refresh_filters()
	_refresh_parts(q)
	for loc in Loadout.LOCS:
		_refresh_loc(loc)
	_refresh_stats(q)
	var changed := not Loadout.same(work, entry)
	_confirm.disabled = not changed
	_revert.disabled = not changed
	_vname.text = camp.loadout_name(m, work) if changed else String(camp.loadout(m)["name"])
	var s := Loadout.stats(GameData, chassis, work)
	_ton_fig["value"].text = "%.1f / %d t" % [s["tons"], int(s["tonnage"])]
	_ton_fig["bar"].value = s["tons"] / maxf(1.0, s["tonnage"])
	_cash_fig["value"].text = BayKit.money(camp.c_bills - int(q["cost"]))


func _refresh_filters() -> void:
	for c in _filters.get_children():
		c.queue_free()
	for f in FILTERS:
		var b := kit.button(f[1], func():
			filter = f[0]
			_refresh())
		b.add_theme_font_size_override("font_size", kit.px(0.85))
		if filter == f[0]:
			var s := StyleBoxFlat.new()
			s.bg_color = Color(UiStyle.HUD_EDGE, 0.22)
			s.border_color = UiStyle.HUD_EDGE
			s.set_border_width_all(1)
			s.content_margin_left = kit.em(0.7)
			s.content_margin_right = kit.em(0.7)
			s.content_margin_top = kit.em(0.25)
			s.content_margin_bottom = kit.em(0.25)
			for st in ["normal", "hover", "pressed"]:
				b.add_theme_stylebox_override(st, s)
		else:
			b.add_theme_color_override("font_color", UiStyle.HUD_DIM)
		_filters.add_child(b)


func _refresh_parts(q: Dictionary) -> void:
	for c in _plist.get_children():
		c.queue_free()
	for id in _part_ids(q):
		var c := _comp(id)
		var k := Loadout.kind(c)
		if filter != "all" and k != filter:
			continue
		var w: Dictionary = c.get("weapon", {})
		var name_box := kit.hbox(0.35)
		var n := kit.label(_nm(id), "body600", 1.0)
		name_box.add_child(n)
		if w.has("range"):
			name_box.add_child(kit.range_mark(String(w["range"])))
		var have := _have(q, id)
		var own := kit.label("×%d" % have if have > 0 else BayKit.money(int(c.get("rp", 0))), "mono", 0.85,
			UiStyle.HUD_OK if have > 0 else UiStyle.HUD_DIM)
		own.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		var heat := "–"
		if not w.is_empty():
			heat = str(int(w.get("heat", 0)))
		elif String(c.get("form", "")) == "HeatSink":
			heat = "+%d" % int(c.get("heatsink", {}).get("dissipation", 4))
		var dmg := ("%s" % _num(float(w["damage"]))) if w.has("damage") else "–"
		var row := PanelContainer.new()
		var s := StyleBoxFlat.new()
		s.bg_color = Color(UiStyle.HUD_EDGE, 0.16) if sel == id else Color(0, 0, 0, 0)
		s.border_color = UiStyle.HUD_EDGE if sel == id else Color(0, 0, 0, 0)
		s.set_border_width_all(1)
		s.content_margin_left = kit.em(0.4)
		s.content_margin_right = kit.em(0.4)
		s.content_margin_top = kit.em(0.3)
		s.content_margin_bottom = kit.em(0.3)
		row.add_theme_stylebox_override("panel", s)
		row.mouse_filter = Control.MOUSE_FILTER_STOP
		row.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		row.gui_input.connect(func(e):
			if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
				sel = -1 if sel == id else id
				msg = _pick_text(id) if sel >= 0 else {"t": "Pick a part on the left to see where it fits.", "k": ""}
				_refresh())
		var b := kit.badge(k)
		b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(_part_columns([b, name_box, "%.1f" % float(c.get("tons", 0.0)), str(int(c.get("crits", 0))), dmg, heat, own]))
		_plist.add_child(row)


static func _num(v: float) -> String:
	return str(int(v)) if is_equal_approx(v, roundf(v)) else "%.1f" % v


func _refresh_loc(loc: String) -> void:
	var p: PanelContainer = _locs[loc]
	for c in p.get_children():
		c.queue_free()
	var ok := sel >= 0 and Loadout.fits(GameData, chassis, vidx, work, sel, loc) == ""
	var s := StyleBoxFlat.new()
	s.bg_color = UiStyle.HUD_PANEL
	s.border_color = UiStyle.HUD_OK if ok else UiStyle.HUD_EDGE_SOFT
	s.set_border_width_all(1)
	if ok:
		s.shadow_color = Color(UiStyle.HUD_OK, 0.35)
		s.shadow_size = kit.px(0.7)
	s.content_margin_left = kit.em(0.6)
	s.content_margin_right = kit.em(0.6)
	s.content_margin_top = kit.em(0.45)
	s.content_margin_bottom = kit.em(0.5)
	p.add_theme_stylebox_override("panel", s)
	p.modulate = Color(1, 1, 1, 0.55) if sel >= 0 and not ok else Color.WHITE
	p.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND if ok else Control.CURSOR_ARROW
	p.tooltip_text = "" if sel < 0 or ok else Loadout.fits(GameData, chassis, vidx, work, sel, loc)
	var v := kit.vbox(0.35)
	p.add_child(v)
	var head := kit.hbox(0.4)
	var t := kit.label(Loadout.LOC_NAMES[loc], "display600", 0.9, UiStyle.HUD_EDGE, true, 0.12)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(t)
	var inf := Loadout.info(GameData, chassis)
	var hps := kit.hbox(0.2)
	for type in ["B", "E", "M"]:
		var used := Loadout.hardpoints_used(GameData, work, loc, type)
		for i in int(inf["hardpoints"][loc][type]):
			hps.add_child(kit.badge(type, i >= used))
	head.add_child(hps)
	v.add_child(head)
	var bar := BayKit.SlotBar.new()
	bar.custom_minimum_size.y = maxf(3.0, roundf(kit.em(0.45)))
	bar.cap = int(inf["slots"][loc])
	bar.fixed = int(Loadout.fixed_slots(GameData, chassis, vidx)[loc])
	bar.used = Loadout.slots_used(GameData, chassis, vidx, work, loc)
	bar.tooltip_text = "%d of %d slots" % [bar.used, bar.cap]
	v.add_child(bar)
	var items := kit.vbox(0.15)
	v.add_child(items)
	var seen := {}
	var base_count := Loadout.counts({loc: entry[loc]})
	var fresh := 0
	for i in work[loc].size():
		var id: int = work[loc][i]
		seen[id] = int(seen.get(id, 0)) + 1
		var is_new: bool = seen[id] > int(base_count.get(id, 0))
		if is_new:
			fresh += int(_comp(id).get("crits", 0))
		var row := kit.hbox(0.4)
		row.add_child(kit.badge(Loadout.kind(_comp(id))))
		var n := kit.label(_nm(id), "body500", 0.95, UiStyle.HUD_WARN if is_new else UiStyle.HUD_INK)
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.clip_text = true
		row.add_child(n)
		row.add_child(kit.label("%.1f" % float(_comp(id).get("tons", 0.0)), "mono", 0.85, UiStyle.HUD_DIM))
		var x := Button.new()
		x.text = "✕"
		x.flat = true
		x.focus_mode = Control.FOCUS_NONE
		x.tooltip_text = "Remove %s" % String(_comp(id).get("name", ""))
		x.add_theme_color_override("font_color", UiStyle.HUD_DIM)
		x.add_theme_color_override("font_hover_color", UiStyle.HUD_CRIT)
		x.add_theme_font_override("font", UiStyle.font("body500"))
		x.add_theme_font_size_override("font_size", kit.px(0.95))
		for st in ["normal", "hover", "pressed", "focus"]:
			var bs := StyleBoxFlat.new()
			bs.bg_color = Color(0, 0, 0, 0)
			bs.border_color = UiStyle.HUD_CRIT if st == "hover" else Color(0, 0, 0, 0)
			bs.set_border_width_all(1)
			bs.content_margin_left = kit.em(0.3)
			bs.content_margin_right = kit.em(0.3)
			x.add_theme_stylebox_override(st, bs)
		var idx: int = i
		x.pressed.connect(func(): _remove(loc, idx))
		row.add_child(x)
		items.add_child(row)
	bar.fresh = fresh
	if work[loc].is_empty():
		var e := kit.label("empty", "body400", 0.88, UiStyle.HUD_DIM)
		items.add_child(e)


func _stat(label: String, value: String, delta: float, digits: int, inverse := false) -> HBoxContainer:
	var h := kit.hbox(0.4)
	var l := kit.label(label, "display600", 0.85, UiStyle.HUD_DIM, true, 0.1)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(l)
	h.add_child(kit.label(value, "mono", 1.0, UiStyle.HUD_INK))
	if absf(delta) > 0.000001:
		var up := delta < 0.0 if inverse else delta > 0.0
		var fmt := "%+." + str(digits) + "f"
		h.add_child(kit.label(fmt % delta, "mono", 1.0, UiStyle.HUD_OK if up else UiStyle.HUD_CRIT))
	return h


func _bar(value: float, ghost := -1.0, colour := UiStyle.HUD_EDGE) -> BayKit.StatBar:
	var b := BayKit.StatBar.new()
	b.custom_minimum_size.y = maxf(2.0, roundf(kit.em(0.45)))
	b.value = value
	b.ghost = ghost
	b.colour = colour
	return b


func _refresh_stats(q: Dictionary) -> void:
	for c in _stats.get_children():
		c.queue_free()
	var s0 := Loadout.stats(GameData, chassis, Loadout.stock_parts(GameData, chassis, vidx))
	var s1 := Loadout.stats(GameData, chassis, work)
	var blocks := [
		[_stat("Tonnage", "%.1f / %d t" % [s1["tons"], int(s1["tonnage"])], s1["tons"] - s0["tons"], 1),
			_bar(s1["tons"] / maxf(1.0, s1["tonnage"]))],
		[_stat("Alpha damage", "%.1f" % s1["alpha"], s1["alpha"] - s0["alpha"], 1), _bar(s1["alpha"] / 40.0, s0["alpha"] / 40.0)],
		[_stat("Damage / sec", "%.2f" % s1["dps"], s1["dps"] - s0["dps"], 2), _bar(s1["dps"] / 8.0, s0["dps"] / 8.0)],
	]
	var hb := _bar(s1["heat"] / maxf(1.0, s1["heat_cap"]))
	hb.heat = true
	hb.over = s1["heat"] > s1["heat_cap"]
	blocks.append([_stat("Alpha heat", "%d / %d" % [int(s1["heat"]), int(s1["heat_cap"])], s1["heat"] - s0["heat"], 0, true), hb])
	blocks.append([_stat("Armour", "%d / %d" % [int(s1["armor"]), int(s1["max_armor"])], s1["armor"] - s0["armor"], 0),
		_bar(s1["armor"] / maxf(1.0, s1["max_armor"]), -1.0, UiStyle.HUD_OK)])
	for b in blocks:
		var v := kit.vbox(0.25)
		for n in b:
			v.add_child(n)
		_stats.add_child(v)
	var sp := kit.vbox(0.25)
	sp.add_child(_stat("Top speed", "%d km/h" % int(s1["speed"]), 0.0, 0))
	sp.add_child(_stat("Longest range", Loadout.RANGE_NAMES[int(s1["range"])], 0.0, 0))
	if s1["jump"]:
		sp.add_child(_stat("Jump jets", "fitted", 0.0, 0))
	_stats.add_child(sp)
	# reason line
	var box := PanelContainer.new()
	var bs := StyleBoxFlat.new()
	bs.bg_color = Color(0, 0, 0, 0)
	bs.border_color = UiStyle.HUD_CRIT if msg["k"] == "bad" else (UiStyle.HUD_OK if msg["k"] == "good" else UiStyle.HUD_EDGE_SOFT)
	bs.set_border_width_all(1)
	bs.content_margin_left = kit.em(0.6)
	bs.content_margin_right = kit.em(0.6)
	bs.content_margin_top = kit.em(0.45)
	bs.content_margin_bottom = kit.em(0.45)
	box.add_theme_stylebox_override("panel", bs)
	box.custom_minimum_size.y = kit.em(2.6)
	var over: bool = s1["heat"] > s1["heat_cap"] and msg["k"] != "bad"
	var text := ("Alpha heat is over capacity: allowed, but this 'Mech will run hot. " if over else "") + String(msg["t"])
	box.add_child(kit.para(text, 20.5, "body400", 0.95, UiStyle.HUD_DIM if msg["k"] == "" else UiStyle.HUD_INK))
	_stats.add_child(box)
	# bill
	var g := GridContainer.new()
	g.columns = 2
	g.add_theme_constant_override("h_separation", kit.px(0.6))
	g.add_theme_constant_override("v_separation", kit.px(0.2))
	var n_from := 0
	for id in q["from_stores"]:
		n_from += int(q["from_stores"][id])
	var n_to := 0
	for id in q["to_stores"]:
		n_to += int(q["to_stores"][id])
	for row in [["Parts bought", "%s C" % BayKit.money(int(q["cost"])), false], ["Fitted from stores", str(n_from), false],
			["Sent to stores", str(n_to), false], ["Refit cost", "%s C" % BayKit.money(int(q["cost"])), true]]:
		var l := kit.label(row[0], "mono", 0.9 * (1.1 if row[2] else 1.0), UiStyle.HUD_EDGE if row[2] else UiStyle.HUD_DIM)
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		g.add_child(l)
		var r := kit.label(row[1], "mono", 0.9 * (1.1 if row[2] else 1.0), UiStyle.HUD_EDGE if row[2] else UiStyle.HUD_INK)
		r.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		g.add_child(r)
	_stats.add_child(g)


# --- save variant ----------------------------------------------------------------------------

func _open_save() -> void:
	if _overlay:
		_overlay.queue_free()
	var p := kit.panel("Save variant", String(GameData.chassis[chassis]["name"]))
	kit.place(p["panel"], 0.38, 0.36, 0.695, 0.36)
	add_child(p["panel"])
	_overlay = p["panel"]
	var mm := kit.margin(1.0, 0.8, 1.0, 0.8)
	p["body"].add_child(mm)
	var v := kit.vbox(0.6)
	mm.add_child(v)
	v.add_child(kit.para("Name this loadout. The bay can then apply it to any other %s." % String(GameData.chassis[chassis]["name"]),
		30, "body400", 1.0, UiStyle.HUD_DIM))
	var line := LineEdit.new()
	var n := camp.variants_for(chassis).size() + 1
	var pilot := String(m["pilot"])
	line.text = ("%s's %s" % [camp.pilots[pilot]["name"], GameData.chassis[chassis]["name"]]) if pilot != "" and camp.pilots.has(pilot) \
		else "%s Custom %d" % [GameData.chassis[chassis]["name"], n]
	line.max_length = 32
	v.add_child(line)
	var h := kit.hbox(0.5)
	var save := func():
		if camp.save_variant(chassis, line.text, work):
			Flow.save_progress()
			msg = {"t": "Saved as %s. Apply it to another %s from the bay." % [line.text.strip_edges(), GameData.chassis[chassis]["name"]], "k": "good"}
		else:
			msg = {"t": "That name is empty or belongs to a designer variant.", "k": "bad"}
		_overlay.queue_free()
		_overlay = null
		_refresh()
	var ok := kit.button("Save", save, true)
	ok.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(ok)
	var cancel := kit.button("Cancel", func():
		_overlay.queue_free()
		_overlay = null)
	cancel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(cancel)
	v.add_child(h)
	line.text_submitted.connect(func(_t): save.call())
	line.grab_focus.call_deferred()
