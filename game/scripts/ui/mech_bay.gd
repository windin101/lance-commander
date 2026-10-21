class_name MechBay
extends Control
## Mech Bay (campaign-layer.md 3; issue I86 mock-up, in the mission HUD's framed panels):
##   top        title, operation and mission, drop weight against the limit, C-Bills
##   left       hangar roster: every 'Mech with its pilot, variant and status; Buy 'Mechs
##              and Pilots
##   centre     the selected 'Mech's HD model and name plate
##   right      its pilot and skills, rating bars and loadout by location; Open Mech Lab,
##              Deploy / Withdraw, Assign pilot, Sell, Apply variant
##   market     Buy 'Mechs swaps the roster for the mission's offers (cards with thumbnail,
##              class, price, hardpoints) and the summary for the selected offer's
##              description, ratings, stock loadout, stats and Buy; a bought 'Mech joins
##              the lance when it fits the slots and drop weight, else the reserve
##   bottom     the deployment strip (3 lances of 4 slots) and Launch
## Rules as before: deploy within the drop weight and the 12-slot cap, a pilot per deployed
## 'Mech (Pilot Ready), sell reserve 'Mechs, buy from the mission's purchase list, Launch
## when every deployed 'Mech has a pilot. Buying, selling and the lab need PlayPurchasing.
## Dev: --sample-campaign fills the bay with mission 2's lance for screenshots;
## --open=buy|pilots|assign|variants opens that list; --open=market --offer=<chassis>
## opens the market on that offer.

var mission := ""
var camp: Campaign
var kit: BayKit
var paint: Array = []
var stage: MechStage
var thumbs: MechStage.Thumbs
var _sel := -1  # selected mech id
var _shown_chassis := ""
var _roster_list: VBoxContainer
var _roster_small: Label
var _summary_body: VBoxContainer
var _summary_title: Label
var _summary_small: Label
var _foot: GridContainer
var _plate_name: Label
var _plate_sub: Label
var _drop_fig: Dictionary
var _cash_fig: Dictionary
var _deploy_count: Label
var _lances: HBoxContainer
var _problem: Label
var _launch: Button
var _overlay: Control
var _msg := ""
var _roster_panel: Control
var _summary_panel: Control
# the market (Buy 'Mechs): offer list in the roster's place, detail in the summary's
var mode := "hangar"  # or "market"
var offer: Dictionary = {}  # the selected purchasable() entry
var _market_panel: Control
var _market_list: VBoxContainer
var _market_small: Label
var _offer_panel: Control
var _offer_title: Label
var _offer_small: Label
var _offer_body: VBoxContainer
var _offer_foot: VBoxContainer
var buy_button: Button
var buy_note: Label  # where a purchase goes, or why it can't be made


## mission 2's lance as the mock-up shows it (dev screenshots); returns the mission.
static func dev_sample(c: Campaign) -> String:
	c.reset()
	c.add_mech("bushwacker", 0, "pmwhacksaw", 1)
	c.add_mech("bushwacker", 0, "pmwlongshot", 2)
	c.add_mech("urbanmech", 0, "pmwflash", 3)
	c.add_mech("werewolf", 0, "", 0)
	c.stores = {156: 2, 120: 1, 7: 1}
	return "mc2_02"


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mission = Flow.current
	camp = Flow.campaign
	if OS.get_cmdline_user_args().has("--sample-campaign"):  # dev: screenshot without playing mc2_01
		mission = dev_sample(camp)
		Flow.current = mission
	var vh := get_viewport().get_visible_rect().size.y if get_viewport() else 1080.0
	kit = BayKit.new(UiStyle.hud_unit(vh))
	theme = UiStyle.hud_theme(kit.u)
	paint = BayKit.player_paint(mission)
	var bg := ColorRect.new()
	bg.color = Color("#0b141b")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	add_child(BayKit.Backdrop.new())
	thumbs = MechStage.Thumbs.new()
	add_child(thumbs)
	_build()
	if Flow.lab_mech_id >= 0 and _mech(Flow.lab_mech_id):
		_sel = Flow.lab_mech_id
	_refresh()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--open="):
			match a.trim_prefix("--open="):
				"buy": _open_buy()
				"market":
					_open_buy()
					for o in camp.purchasable(mission):  # --offer=<chassis> picks one
						for b in OS.get_cmdline_user_args():
							if b == "--offer=" + String(o["chassis"]):
								select_offer(o)
				"pilots": _open_pilots()
				"assign": _open_assign()
				"variants": _open_variants()


func _purchasing() -> bool:
	return bool(camp.mission_info(mission).get("PlayPurchasing", true))


func _mech(id: int) -> Dictionary:
	for m in camp.mechs:
		if int(m["id"]) == id:
			return m
	return {}


func _sorted() -> Array:
	var list := camp.mechs.duplicate()
	list.sort_custom(func(a, b): return (a["slot"] if a["slot"] > 0 else 99) < (b["slot"] if b["slot"] > 0 else 99))
	return list


# --- layout ------------------------------------------------------------------------------

func _build() -> void:
	# top bar
	var top := PanelContainer.new()
	top.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	kit.place(top, 0.01, 0.016, 0.99, 0.016)
	add_child(top)
	var tm := kit.margin(1.4, 0.7, 1.4, 0.7)
	top.add_child(tm)
	var th := kit.hbox(2.4)
	tm.add_child(th)
	var title := kit.hbox(1.0)
	title.add_child(kit.label("Mech Bay", "display700", 1.5, UiStyle.HUD_INK, true, 0.14))
	var info: Dictionary = Flow.info(mission)
	var sub := kit.label("Operation %d · %s" % [int(info.get("group", 0)) + 1, MissionBrief.load_mission(GameData, mission).title],
		"display500", 0.9, UiStyle.HUD_DIM, true, 0.1)
	sub.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	title.add_child(sub)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	th.add_child(title)
	_drop_fig = kit.fig("Drop weight", true)
	th.add_child(_drop_fig["box"])
	_cash_fig = kit.fig("C-Bills")
	th.add_child(_cash_fig["box"])
	var back := kit.button("Briefing", func(): Flow.goto_briefing(mission))
	back.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	th.add_child(back)

	# roster
	var roster := kit.panel("Hangar", "")
	_roster_small = roster["small"]
	_roster_panel = roster["panel"]
	kit.place(roster["panel"], 0.01, 0.13, 0.01, 0.845, 30.0)
	add_child(roster["panel"])
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	roster["body"].add_child(scroll)
	var rm := kit.margin(0.6, 0.6, 0.6, 0.6)
	rm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(rm)
	_roster_list = kit.vbox(0.5)
	_roster_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rm.add_child(_roster_list)
	roster["body"].add_child(kit.rule())
	var rf := kit.margin(0.6, 0.6, 0.6, 0.6)
	roster["body"].add_child(rf)
	var rfh := GridContainer.new()
	rfh.columns = 2
	rfh.add_theme_constant_override("h_separation", kit.px(0.5))
	rf.add_child(rfh)
	var buy := kit.button("Buy 'Mechs", _open_buy)
	buy.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	buy.disabled = not _purchasing()
	rfh.add_child(buy)
	var pil := kit.button("Pilots", _open_pilots)
	pil.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rfh.add_child(pil)

	# the 'Mech
	stage = MechStage.new()
	kit.place(stage, 0.33, 0.135, 0.67, 0.77)
	stage.spin = 6.0
	add_child(stage)
	var plate := kit.vbox(0.1)
	plate.anchor_left = 0.5
	plate.anchor_right = 0.5
	plate.anchor_top = 0.835
	plate.anchor_bottom = 0.835
	plate.grow_horizontal = Control.GROW_DIRECTION_BOTH
	plate.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_plate_name = kit.label("", "display700", 2.1, UiStyle.HUD_INK, true, 0.18)
	_plate_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	plate.add_child(_plate_name)
	_plate_sub = kit.label("", "display500", 0.95, UiStyle.HUD_DIM, true, 0.14)
	_plate_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	plate.add_child(_plate_sub)
	add_child(plate)

	# summary
	var sum := kit.panel("Loadout", "")
	_summary_panel = sum["panel"]
	_summary_title = sum["title"]
	_summary_small = sum["small"]
	kit.place(sum["panel"], 0.99, 0.13, 0.99, 0.845, 32.0, true)
	add_child(sum["panel"])
	var ss := ScrollContainer.new()
	ss.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	ss.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sum["body"].add_child(ss)
	var sm := kit.margin(1.0, 0.8, 1.0, 0.8)
	sm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ss.add_child(sm)
	_summary_body = kit.vbox(0.9)
	_summary_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sm.add_child(_summary_body)
	sum["body"].add_child(kit.rule())
	var sf := kit.margin(0.7, 0.7, 0.7, 0.7)
	sum["body"].add_child(sf)
	_foot = GridContainer.new()
	_foot.columns = 2
	_foot.add_theme_constant_override("h_separation", kit.px(0.5))
	_foot.add_theme_constant_override("v_separation", kit.px(0.5))
	sf.add_child(_foot)

	_build_market()

	# deployment strip
	var dep := PanelContainer.new()
	dep.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	kit.place(dep, 0.01, 0.984, 0.99, 0.984)
	dep.grow_vertical = Control.GROW_DIRECTION_BEGIN
	add_child(dep)
	var dm := kit.margin(1.0, 0.6, 1.0, 0.6)
	dep.add_child(dm)
	var dh := kit.hbox(1.2)
	dm.add_child(dh)
	var lbl := kit.vbox(0.2)
	lbl.custom_minimum_size.x = kit.em(8)
	lbl.add_child(kit.label("Deployment", "display600", 0.85, UiStyle.HUD_DIM, true, 0.14))
	_deploy_count = kit.label("", "mono", 1.3, UiStyle.HUD_INK)
	lbl.add_child(_deploy_count)
	lbl.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	dh.add_child(lbl)
	_lances = kit.hbox(1.0)
	_lances.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	dh.add_child(_lances)
	var lv := kit.vbox(0.3)
	lv.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_problem = kit.label("", "body500", 0.95, UiStyle.HUD_WARN)
	_problem.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	lv.add_child(_problem)
	_launch = kit.button("Launch", func():
		Flow.save_progress()
		Flow.launch(), true)
	_launch.custom_minimum_size.x = kit.em(10)
	_launch.size_flags_horizontal = Control.SIZE_SHRINK_END
	lv.add_child(_launch)
	dh.add_child(lv)


# --- refresh -------------------------------------------------------------------------------

func _refresh() -> void:
	if _sel < 0 or _mech(_sel).is_empty():
		var list := _sorted()
		_sel = int(list[0]["id"]) if not list.is_empty() else -1
	_refresh_top()
	var market := mode == "market"
	_roster_panel.visible = not market
	_summary_panel.visible = not market
	_market_panel.visible = market
	_offer_panel.visible = market
	if market:
		_refresh_market()
	else:
		_refresh_roster()
		_refresh_summary()
	_refresh_deploy()


func _refresh_top() -> void:
	var limit := camp.drop_limit(mission)
	var t := camp.deployed_tonnage()
	_drop_fig["value"].text = "%d / %d t" % [int(t), int(limit)]
	_drop_fig["value"].add_theme_color_override("font_color", UiStyle.HUD_CRIT if t > limit + 0.01 else UiStyle.HUD_EDGE)
	_drop_fig["bar"].value = t / maxf(1.0, limit)
	_drop_fig["bar"].over = t > limit + 0.01
	_cash_fig["value"].text = BayKit.money(camp.c_bills)


func _refresh_roster() -> void:
	for c in _roster_list.get_children():
		c.queue_free()
	var list := _sorted()
	_roster_small.text = "%d 'Mechs · %d deployed" % [list.size(), camp.deployed().size()]
	for m in list:
		_roster_list.add_child(_roster_row(m))
	if list.is_empty():
		_roster_list.add_child(kit.para("No 'Mechs. Buy some from the purchase list.", 26, "body500", 1.0, UiStyle.HUD_WARN))


func _status(m: Dictionary) -> Array:
	if int(m["slot"]) == 0:
		return ["Reserve", UiStyle.HUD_DIM]
	if String(m["pilot"]) == "":
		return ["No pilot", UiStyle.HUD_WARN]
	return ["Ready", UiStyle.HUD_OK]


func _variant_short(m: Dictionary) -> String:
	var n := String(camp.loadout(m)["name"])
	var cn := String(GameData.chassis.get(String(m["chassis"]), {}).get("name", ""))
	return n.substr(cn.length()).strip_edges() if cn != "" and n.begins_with(cn) and n.length() > cn.length() else n


func _chassis_name(m: Dictionary) -> String:
	return String(GameData.chassis.get(String(m["chassis"]), {}).get("name", m["chassis"]))


func _pilot_name(p: String) -> String:
	return String(camp.pilots.get(p, {}).get("name", p))


func _thumb(m: Dictionary, size_em: float) -> Control:
	var box := Control.new()
	box.custom_minimum_size = Vector2(kit.em(size_em), kit.em(size_em))
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var glow := TextureRect.new()
	var g := Gradient.new()
	g.set_color(0, Color(UiStyle.HUD_EDGE, 0.16))
	g.set_color(1, Color(UiStyle.HUD_EDGE, 0.0))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	glow.texture = gt
	glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(glow)
	var tr := TextureRect.new()
	tr.set_anchors_preset(Control.PRESET_FULL_RECT)
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(tr)
	var ref: WeakRef = weakref(tr)  # cards are rebuilt; the shot may land after this one is gone
	thumbs.request(String(m["chassis"]), paint, func(tex):
		var t: TextureRect = ref.get_ref()
		if t:
			t.texture = tex)
	return box


func _roster_row(m: Dictionary) -> Control:
	var sel := int(m["id"]) == _sel
	var row := PanelContainer.new()
	var s := StyleBoxFlat.new()
	s.bg_color = UiStyle.HUD_PANEL_2 if not sel else UiStyle.HUD_PANEL_2.lerp(UiStyle.HUD_EDGE, 0.12)
	s.border_color = UiStyle.HUD_EDGE if sel else Color(UiStyle.HUD_EDGE, 0.18)
	s.set_border_width_all(1)
	if sel:
		s.shadow_color = Color(UiStyle.HUD_GLOW, 0.3)
		s.shadow_size = kit.px(0.4)
	s.content_margin_left = kit.em(0.7)
	s.content_margin_right = kit.em(0.7)
	s.content_margin_top = kit.em(0.5)
	s.content_margin_bottom = kit.em(0.5)
	row.add_theme_stylebox_override("panel", s)
	row.mouse_filter = Control.MOUSE_FILTER_STOP
	row.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row.gui_input.connect(func(e):
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			_select(int(m["id"])))
	var h := kit.hbox(0.8)
	row.add_child(h)
	var th := _thumb(m, 4.6)
	if int(m["slot"]) > 0:
		var tag := PanelContainer.new()
		var ts := StyleBoxFlat.new()
		ts.bg_color = UiStyle.HUD_EDGE
		ts.content_margin_left = kit.em(0.35)
		ts.content_margin_right = kit.em(0.35)
		tag.add_theme_stylebox_override("panel", ts)
		tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
		tag.add_child(kit.label(str(int(m["slot"])), "display700", 0.85, Color(0.012, 0.063, 0.09)))
		tag.position = Vector2(-kit.em(0.7), -kit.em(0.5))
		th.add_child(tag)
	h.add_child(th)
	var info := kit.vbox(0.2)
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var pilot := String(m["pilot"])
	info.add_child(kit.label(_pilot_name(pilot) if pilot != "" else "No pilot", "display600", 1.15, UiStyle.HUD_INK, true, 0.05))
	var cn := _chassis_name(m)
	info.add_child(kit.label("%s · %s · %d t" % [cn, _variant_short(m), int(camp.tonnage(m["chassis"]))], "body500", 0.95, UiStyle.HUD_DIM))
	var n_parts := 0
	for loc in Loadout.LOCS:
		n_parts += camp.loadout(m)["parts"][loc].size()
	info.add_child(kit.label("%s C    %d parts" % [BayKit.money(camp.mech_value(m)), n_parts], "mono", 0.88, UiStyle.HUD_DIM))
	h.add_child(info)
	var st := _status(m)
	h.add_child(kit.chip(st[0], st[1]))
	return row


func _select(id: int) -> void:
	_sel = id
	_msg = ""
	_close_overlay()
	_refresh()


func _refresh_summary() -> void:
	for c in _summary_body.get_children():
		c.queue_free()
	for c in _foot.get_children():
		c.queue_free()
	var m := _mech(_sel)
	if m.is_empty():
		_summary_small.text = ""
		_plate_name.text = ""
		_plate_sub.text = ""
		stage.visible = false
		return
	stage.visible = true
	var chassis := String(m["chassis"])
	if chassis != _shown_chassis:
		stage.show_mech(chassis, paint)
		_shown_chassis = chassis
	var lo := camp.loadout(m)
	var st := Loadout.stats(GameData, chassis, lo["parts"])
	_plate_name.text = _chassis_name(m)
	_plate_sub.text = "%s · %d t" % [lo["name"], int(camp.tonnage(chassis))]
	_summary_small.text = "%d t · %d km/h" % [int(camp.tonnage(chassis)), int(st["speed"])]
	# pilot line
	var pl := kit.hbox(0.8)
	var face := TextureRect.new()
	face.texture = PilotPortraits.texture_for(String(m["pilot"]))
	face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	face.custom_minimum_size = Vector2(kit.em(4), kit.em(4 * 46.0 / 33.0))
	pl.add_child(face)
	var pv := kit.vbox(0.25)
	pv.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var pilot := String(m["pilot"])
	pv.add_child(kit.label(_pilot_name(pilot) if pilot != "" else "No pilot assigned", "display600", 1.2, UiStyle.HUD_INK, true, 0.06))
	var sk := kit.hbox(1.6)
	if pilot != "":
		var pd: Dictionary = camp.pilots.get(pilot, {})
		for pair in [["Gun", str(int(pd.get("gunnery", 0)))], ["Plt", str(int(pd.get("piloting", 0)))], ["Rank", Campaign.rank(pd)],
				["Kills", str(int(pd.get("kills", 0)))]]:
			var one := kit.hbox(0.35)
			one.add_child(kit.label(pair[0], "mono", 0.85, UiStyle.HUD_DIM, true))
			one.add_child(kit.label(pair[1], "mono", 0.85, UiStyle.HUD_INK))
			sk.add_child(one)
	else:
		sk.add_child(kit.label("Reserve: not deployed" if int(m["slot"]) == 0 else "Assign a pilot to launch", "mono", 0.85, UiStyle.HUD_DIM))
	pv.add_child(sk)
	pl.add_child(pv)
	_summary_body.add_child(pl)
	# ratings
	var g := _rating_grid(st)
	_summary_body.add_child(g)
	# loadout by location
	var ld := GridContainer.new()
	ld.columns = 3
	ld.add_theme_constant_override("h_separation", kit.px(0.6))
	ld.add_theme_constant_override("v_separation", kit.px(0.25))
	for loc in Loadout.LOCS:
		var c := Loadout.counts({loc: lo["parts"][loc]})
		var ids: Array = []
		for id in lo["parts"][loc]:
			if not ids.has(id):
				ids.append(id)
		for id in ids:
			var comp := Loadout.component(GameData, id)
			var l := kit.label(Loadout.LOC_SHORT[loc], "mono", 0.85, UiStyle.HUD_DIM)
			l.custom_minimum_size.x = kit.em(3.0)
			ld.add_child(l)
			var nm := kit.label(Loadout.short_name(String(comp.get("name", "?"))) + (" ×%d" % c[id] if c[id] > 1 else ""), "body500", 1.0)
			nm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			ld.add_child(nm)
			var t := kit.label("%.1f t" % (float(comp.get("tons", 0.0)) * c[id]), "mono", 0.85, UiStyle.HUD_DIM)
			t.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			ld.add_child(t)
	_summary_body.add_child(ld)
	if _msg != "":
		_summary_body.add_child(kit.para(_msg, 28, "body500", 1.0, UiStyle.HUD_WARN))
	# buttons
	var deployed := int(m["slot"]) > 0
	var lab_ok := _purchasing() and Loadout.lab_allowed(GameData, chassis)
	var lab := kit.button("Open Mech Lab", func(): Flow.goto_mech_lab(int(m["id"])), true)
	lab.disabled = not lab_ok
	lab.tooltip_text = "" if lab_ok else "The Mech Lab opens on missions with purchasing"
	lab.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_foot.add_child(lab)
	var variant := kit.button("Apply variant", _open_variants)
	variant.disabled = not lab_ok
	variant.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_foot.add_child(variant)
	var dep := kit.button("Withdraw" if deployed else "Deploy", func():
		if deployed:
			camp.withdraw(m)
		elif not camp.deploy(m, mission):
			_msg = "Can't deploy: %s." % ("all 12 slots are full" if camp.deployed().size() >= Campaign.MAX_DEPLOY else "over the drop weight")
		_refresh())
	dep.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_foot.add_child(dep)
	var assign := kit.button("Assign pilot", _open_assign)
	assign.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_foot.add_child(assign)
	var sell := kit.button("Sell · %s C" % BayKit.money(camp.mech_value(m)), func():
		camp.sell(m)
		_sel = -1
		_refresh())
	sell.disabled = deployed or not _purchasing()
	sell.tooltip_text = "Only reserve 'Mechs can be sold" if deployed else ""
	sell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_foot.add_child(sell)


func _refresh_deploy() -> void:
	for c in _lances.get_children():
		c.queue_free()
	var by_slot := {}
	for d in camp.deployed():
		by_slot[int(d["slot"])] = d
	for lance in 3:
		var g := kit.hbox(0.35)
		g.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		for i in 4:
			var n := lance * 4 + i + 1
			var cell := PanelContainer.new()
			cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			cell.custom_minimum_size.y = kit.em(3.4)
			var s := StyleBoxFlat.new()
			var on := by_slot.has(n)
			var sel := on and int(by_slot[n]["id"]) == _sel
			s.bg_color = Color(UiStyle.HUD_EDGE, 0.08) if on else Color(1, 1, 1, 0.02)
			s.border_color = UiStyle.HUD_EDGE if sel else (UiStyle.HUD_EDGE_SOFT if on else Color(UiStyle.HUD_EDGE, 0.2))
			s.set_border_width_all(1)
			cell.add_theme_stylebox_override("panel", s)
			var inner := Control.new()
			inner.mouse_filter = Control.MOUSE_FILTER_IGNORE
			cell.add_child(inner)
			if on:
				var m: Dictionary = by_slot[n]
				var th := _thumb(m, 3.4)
				th.set_anchors_preset(Control.PRESET_FULL_RECT)
				inner.add_child(th)
				cell.mouse_filter = Control.MOUSE_FILTER_STOP
				cell.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
				cell.tooltip_text = "%s · %s" % [_chassis_name(m), _pilot_name(String(m["pilot"])) if String(m["pilot"]) != "" else "no pilot"]
				cell.gui_input.connect(func(e):
					if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
						_select(int(m["id"])))
			var num := kit.label(str(n), "mono", 0.75, UiStyle.HUD_DIM)
			num.position = Vector2(kit.em(0.25), kit.em(0.05))
			inner.add_child(num)
			g.add_child(cell)
		_lances.add_child(g)
	_deploy_count.text = "%d / %d" % [camp.deployed().size(), Campaign.MAX_DEPLOY]
	var problem := camp.launch_problem(mission)
	_problem.text = problem
	_launch.disabled = problem != ""
	_launch.tooltip_text = problem


# --- overlays --------------------------------------------------------------------------------

func _close_overlay() -> void:
	if _overlay:
		_overlay.queue_free()
		_overlay = null
	stage.visible = not _mech(_sel).is_empty()


## A framed list over the centre of the bay; returns its list box.
func _overlay_panel(title: String, small: String) -> VBoxContainer:
	_close_overlay()
	stage.visible = false
	var p := kit.panel(title, small)
	kit.place(p["panel"], 0.335, 0.14, 0.665, 0.76)
	add_child(p["panel"])
	_overlay = p["panel"]
	var sc := ScrollContainer.new()
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	p["body"].add_child(sc)
	var mm := kit.margin(0.9, 0.7, 0.9, 0.7)
	mm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sc.add_child(mm)
	var list := kit.vbox(0.45)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mm.add_child(list)
	p["body"].add_child(kit.rule())
	var fm := kit.margin(0.7, 0.6, 0.7, 0.6)
	p["body"].add_child(fm)
	var close := kit.button("Close", _close_overlay)
	close.size_flags_horizontal = Control.SIZE_SHRINK_END
	fm.add_child(close)
	return list


func _overlay_row(text: String, sub: String, action: String, enabled: bool, on_press: Callable) -> Control:
	var h := kit.hbox(0.8)
	var v := kit.vbox(0.1)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_child(kit.label(text, "display600", 1.05, UiStyle.HUD_INK, false, 0.04))
	v.add_child(kit.label(sub, "mono", 0.85, UiStyle.HUD_DIM))
	h.add_child(v)
	if action != "":
		var b := kit.button(action, on_press)
		b.disabled = not enabled
		b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(b)
	return h


func _open_buy() -> void:
	_close_overlay()
	mode = "market"
	var offers := camp.purchasable(mission)
	if offer.is_empty() or not offers.any(func(o): return _same_offer(o, offer)):
		offer = offers[0] if not offers.is_empty() else {}
	_refresh()


func _close_market() -> void:
	mode = "hangar"
	_refresh()


static func _same_offer(a: Dictionary, b: Dictionary) -> bool:
	return String(a.get("chassis", "")) == String(b.get("chassis", "")) and int(a.get("variant", -1)) == int(b.get("variant", -1))


func select_offer(o: Dictionary) -> void:
	offer = o
	_refresh()


## Buy the selected offer (Campaign.buy_for: deployed when it fits, else reserve).
func buy_offer() -> Dictionary:
	if offer.is_empty():
		return {}
	var m := camp.buy_for(String(offer["chassis"]), int(offer["variant"]), mission)
	if not m.is_empty():
		_sel = int(m["id"])
		_msg = "Bought %s: %s." % [offer["name"], ("deployed in slot %d" % int(m["slot"])) if int(m["slot"]) > 0 else "in reserve"]
		Flow.save_progress()
	_refresh()
	return m


func _rating_grid(st: Dictionary) -> GridContainer:
	var g := GridContainer.new()
	g.columns = 3
	g.add_theme_constant_override("h_separation", kit.px(0.7))
	g.add_theme_constant_override("v_separation", kit.px(0.45))
	var bars := [["Firepower", st["alpha"] / 40.0, "%d" % roundi(st["alpha"]), false],
		["Sustained", st["dps"] / 8.0, "%.1f" % st["dps"], false],
		["Armour", st["armor"] / 432.0, "%d" % int(st["armor"]), false],
		["Speed", st["speed"] / 130.0, "%d" % int(st["speed"]), false],
		["Heat", st["heat"] / maxf(1.0, st["heat_cap"]), "%d/%d" % [int(st["heat"]), int(st["heat_cap"])], true]]
	for b in bars:
		var n := kit.label(b[0], "display600", 0.88, UiStyle.HUD_DIM, true, 0.1)
		n.custom_minimum_size.x = kit.em(6.5)
		g.add_child(n)
		var bar := BayKit.StatBar.new()
		bar.custom_minimum_size = Vector2(0, maxf(2.0, roundf(kit.em(0.45))))
		bar.value = b[1]
		if b[3]:
			bar.heat = true
			bar.over = b[1] > 1.0
		g.add_child(bar)
		var v := kit.label(b[2], "mono", 0.88, UiStyle.HUD_INK)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		v.custom_minimum_size.x = kit.em(3.6)
		g.add_child(v)
	return g


# --- the market ------------------------------------------------------------------------------

func _build_market() -> void:
	var mk := kit.panel("Market", "")
	_market_panel = mk["panel"]
	_market_small = mk["small"]
	kit.place(mk["panel"], 0.01, 0.13, 0.01, 0.845, 30.0)
	mk["panel"].visible = false
	add_child(mk["panel"])
	var sc := ScrollContainer.new()
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	mk["body"].add_child(sc)
	var mm := kit.margin(0.6, 0.6, 0.6, 0.6)
	mm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sc.add_child(mm)
	_market_list = kit.vbox(0.5)
	_market_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mm.add_child(_market_list)
	mk["body"].add_child(kit.rule())
	var fm := kit.margin(0.6, 0.6, 0.6, 0.6)
	mk["body"].add_child(fm)
	var back := kit.button("Back to hangar", _close_market)
	fm.add_child(back)

	var od := kit.panel("Offer", "")
	_offer_panel = od["panel"]
	_offer_title = od["title"]
	_offer_small = od["small"]
	kit.place(od["panel"], 0.99, 0.13, 0.99, 0.845, 32.0, true)
	od["panel"].visible = false
	add_child(od["panel"])
	var os := ScrollContainer.new()
	os.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	os.size_flags_vertical = Control.SIZE_EXPAND_FILL
	od["body"].add_child(os)
	var om := kit.margin(1.0, 0.8, 1.0, 0.8)
	om.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	os.add_child(om)
	_offer_body = kit.vbox(0.85)
	_offer_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	om.add_child(_offer_body)
	od["body"].add_child(kit.rule())
	var of := kit.margin(0.7, 0.7, 0.7, 0.7)
	od["body"].add_child(of)
	_offer_foot = kit.vbox(0.5)
	of.add_child(_offer_foot)
	buy_note = kit.para("", 29, "body500", 0.95, UiStyle.HUD_DIM)
	_offer_foot.add_child(buy_note)
	var row := GridContainer.new()
	row.columns = 2
	row.add_theme_constant_override("h_separation", kit.px(0.5))
	_offer_foot.add_child(row)
	buy_button = kit.button("Buy", func(): buy_offer(), true)
	buy_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(buy_button)
	var close := kit.button("Back to hangar", _close_market)
	close.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(close)


func _offer_card(o: Dictionary) -> Control:
	var chassis := String(o["chassis"])
	var sel := _same_offer(o, offer)
	var afford := int(o["price"]) <= camp.c_bills
	var card := PanelContainer.new()
	var s := StyleBoxFlat.new()
	s.bg_color = UiStyle.HUD_PANEL_2 if not sel else UiStyle.HUD_PANEL_2.lerp(UiStyle.HUD_EDGE, 0.12)
	s.border_color = UiStyle.HUD_EDGE if sel else Color(UiStyle.HUD_EDGE, 0.18)
	s.set_border_width_all(1)
	if sel:
		s.shadow_color = Color(UiStyle.HUD_GLOW, 0.3)
		s.shadow_size = kit.px(0.4)
	s.content_margin_left = kit.em(0.7)
	s.content_margin_right = kit.em(0.7)
	s.content_margin_top = kit.em(0.5)
	s.content_margin_bottom = kit.em(0.5)
	card.add_theme_stylebox_override("panel", s)
	card.mouse_filter = Control.MOUSE_FILTER_STOP
	card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	card.gui_input.connect(func(e):
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			select_offer(o))
	var h := kit.hbox(0.8)
	card.add_child(h)
	h.add_child(_thumb({"chassis": chassis}, 4.6))
	var v := kit.vbox(0.2)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_child(kit.label(String(o["name"]), "display600", 1.1, UiStyle.HUD_INK, true, 0.05))
	var tons := float(o["tonnage"])
	v.add_child(kit.label("%s · %d t · %s" % [GameData.chassis[chassis]["name"], int(tons), Loadout.weight_class(tons).capitalize()],
		"body500", 0.95, UiStyle.HUD_DIM))
	var hp := kit.hbox(0.25)
	var counts := Loadout.weapon_counts(GameData, Loadout.stock_parts(GameData, chassis, int(o["variant"])))
	for t in ["B", "E", "M"]:
		for i in int(counts[t]):
			hp.add_child(kit.badge(t))
	v.add_child(hp)
	h.add_child(v)
	var price := kit.label("%s C" % BayKit.money(int(o["price"])), "mono", 1.0, UiStyle.HUD_INK if afford else UiStyle.HUD_CRIT)
	price.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	h.add_child(price)
	return card


func _refresh_market() -> void:
	for c in _market_list.get_children():
		c.queue_free()
	for c in _offer_body.get_children():
		c.queue_free()
	var offers := camp.purchasable(mission)
	_market_small.text = "%d offers · %s C" % [offers.size(), BayKit.money(camp.c_bills)]
	for o in offers:
		_market_list.add_child(_offer_card(o))
	if offers.is_empty():
		_market_list.add_child(kit.para("Nothing for sale this mission.", 26, "body500", 1.0, UiStyle.HUD_WARN))
	if offer.is_empty():
		_offer_title.text = "Offer"
		_offer_small.text = ""
		_plate_name.text = ""
		_plate_sub.text = ""
		stage.visible = false
		buy_button.disabled = true
		buy_note.text = ""
		return
	var chassis := String(offer["chassis"])
	var idx := int(offer["variant"])
	stage.visible = true
	if chassis != _shown_chassis:
		stage.show_mech(chassis, paint)
		_shown_chassis = chassis
	var tons := float(offer["tonnage"])
	var parts := Loadout.stock_parts(GameData, chassis, idx)
	var st := Loadout.stats(GameData, chassis, parts)
	var cname := String(GameData.chassis[chassis]["name"])
	_plate_name.text = cname
	_plate_sub.text = "%s · %d t · for sale" % [offer["name"], int(tons)]
	_offer_title.text = String(offer["name"])
	_offer_small.text = "%d t · %s" % [int(tons), Loadout.weight_class(tons)]
	var desc := UiStyle.clean(Loadout.description(GameData, chassis))
	if desc != "":
		_offer_body.add_child(kit.para(desc, 29, "body400", 1.0, UiStyle.HUD_DIM))
	_offer_body.add_child(_rating_grid(st))
	# stock loadout with each location's hardpoints
	var inf := Loadout.info(GameData, chassis)
	var ld := GridContainer.new()
	ld.columns = 3
	ld.add_theme_constant_override("h_separation", kit.px(0.6))
	ld.add_theme_constant_override("v_separation", kit.px(0.3))
	for loc in Loadout.LOCS:
		var hp := kit.hbox(0.2)
		for t in ["B", "E", "M"]:
			var used := Loadout.hardpoints_used(GameData, parts, loc, t)
			for i in int(inf["hardpoints"][loc][t]):
				hp.add_child(kit.badge(t, i >= used))
		if parts[loc].is_empty() and hp.get_child_count() == 0:
			hp.queue_free()
			continue
		var l := kit.label(Loadout.LOC_SHORT[loc], "mono", 0.85, UiStyle.HUD_DIM)
		l.custom_minimum_size.x = kit.em(2.4)
		ld.add_child(l)
		var c := Loadout.counts({loc: parts[loc]})
		var names: Array[String] = []
		for id in c:
			names.append(Loadout.short_name(String(Loadout.component(GameData, id).get("name", "?"))) + (" ×%d" % c[id] if c[id] > 1 else ""))
		var nm := kit.label(", ".join(names) if not names.is_empty() else "–", "body500", 1.0,
			UiStyle.HUD_INK if not names.is_empty() else UiStyle.HUD_DIM)
		nm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		nm.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		ld.add_child(nm)
		ld.add_child(hp)
	_offer_body.add_child(ld)
	var facts := GridContainer.new()
	facts.columns = 2
	facts.add_theme_constant_override("h_separation", kit.px(0.8))
	facts.add_theme_constant_override("v_separation", kit.px(0.2))
	var dest := camp.buy_destination(chassis, mission)
	for f in [["Top speed", "%d km/h" % int(st["speed"])], ["Armour", "%d / %d" % [int(st["armor"]), int(st["max_armor"])]],
			["Alpha heat", "%d / %d" % [int(st["heat"]), int(st["heat_cap"])]], ["Jump jets", "Yes" if st["jump"] else "No"],
			["Longest range", Loadout.RANGE_NAMES[int(st["range"])]],
			["Price", "%s C" % BayKit.money(int(offer["price"]))], ["Your C-Bills", "%s C" % BayKit.money(camp.c_bills)]]:
		var k := kit.label(f[0], "display600", 0.85, UiStyle.HUD_DIM, true, 0.1)
		k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		facts.add_child(k)
		var val := kit.label(f[1], "mono", 1.0, UiStyle.HUD_INK)
		val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		facts.add_child(val)
	_offer_body.add_child(facts)
	if _msg != "":
		_offer_body.add_child(kit.para(_msg, 29, "body500", 1.0, UiStyle.HUD_OK))
	var problem := camp.buy_problem(chassis, idx)
	buy_button.text = ("Buy · %s C" % BayKit.money(int(offer["price"]))).to_upper()
	buy_button.disabled = problem != ""
	buy_button.tooltip_text = problem
	if problem != "":
		buy_note.text = problem + "."
		buy_note.add_theme_color_override("font_color", UiStyle.HUD_CRIT)
	elif dest == "deployed":
		buy_note.text = "Joins the lance in the next free slot: %d / %d t after, %d / %d slots." % [
			int(camp.deployed_tonnage() + tons), int(camp.drop_limit(mission)), camp.deployed().size() + 1, Campaign.MAX_DEPLOY]
		buy_note.add_theme_color_override("font_color", UiStyle.HUD_OK)
	else:
		var why := "all %d slots are full" % Campaign.MAX_DEPLOY if camp.deployed().size() >= Campaign.MAX_DEPLOY \
			else "it would take the drop weight to %d / %d t" % [int(camp.deployed_tonnage() + tons), int(camp.drop_limit(mission))]
		buy_note.text = "Goes to the reserve: %s. %s C left after." % [why, BayKit.money(camp.c_bills - int(offer["price"]))]
		buy_note.add_theme_color_override("font_color", UiStyle.HUD_WARN)


func _open_pilots() -> void:
	var list := _overlay_panel("Pilots", "available this mission")
	var on := {}
	for m in camp.mechs:
		if String(m["pilot"]) != "":
			on[String(m["pilot"])] = m
	for p in camp.available_pilots(mission):
		var d: Dictionary = camp.pilots[p]
		var where := ("in %s (slot %d)" % [_chassis_name(on[p]), int(on[p]["slot"])]) if on.has(p) else "unassigned"
		list.add_child(_overlay_row(String(d["name"]), "%s · GUN %d · PLT %d · %d missions · %d kills · %s" % [Campaign.rank(d),
			int(d["gunnery"]), int(d["piloting"]), int(d["missions"]), int(d["kills"]), where], "", false, func(): pass))


func _open_assign() -> void:
	var m := _mech(_sel)
	if m.is_empty():
		return
	var list := _overlay_panel("Assign pilot", "%s · %s" % [_chassis_name(m), _variant_short(m)])
	if int(m["slot"]) == 0 and not camp.can_deploy(m, mission):
		list.add_child(kit.para("This 'Mech can't be deployed: %s." % ("all 12 slots are full" if camp.deployed().size() >= Campaign.MAX_DEPLOY else "it would go over the drop weight"), 30, "body500", 1.0, UiStyle.HUD_WARN))
		return
	if int(m["slot"]) == 0:
		list.add_child(kit.para("Assigning a pilot deploys this 'Mech in the next free slot.", 30, "body500", 1.0, UiStyle.HUD_DIM))
	var assign := func(p: String):
		if int(m["slot"]) == 0:
			camp.deploy(m, mission)
		m["pilot"] = p
		_close_overlay()
		_refresh()
	if String(m["pilot"]) != "":
		list.add_child(_overlay_row("No pilot", "take %s out of the cockpit" % _pilot_name(String(m["pilot"])), "Clear", true,
			func(): assign.call("")))
	for p in camp.free_pilots(mission):
		if p == String(m["pilot"]):
			continue
		var d: Dictionary = camp.pilots[p]
		list.add_child(_overlay_row(String(d["name"]), "%s · GUN %d · PLT %d · %d kills" % [Campaign.rank(d), int(d["gunnery"]),
			int(d["piloting"]), int(d["kills"])], "Assign", true, func(): assign.call(p)))


func _open_variants() -> void:
	var m := _mech(_sel)
	if m.is_empty():
		return
	var chassis := String(m["chassis"])
	var list := _overlay_panel("Apply variant", "%s · now %s" % [_chassis_name(m), camp.loadout(m)["name"]])
	var options: Array = []
	for v in Loadout.stock_variants(GameData.chassis[chassis]):
		if Loadout.fixed_slots(GameData, chassis, int(v["index"])) == Loadout.fixed_slots(GameData, chassis, int(m["variant"])):
			options.append({"name": String(v["name"]), "chassis": chassis, "parts": Loadout.stock_parts(GameData, chassis, int(v["index"])), "stock": true})
	for sv in camp.variants_for(chassis):
		options.append(sv)
	if camp.variants_for(chassis).is_empty():
		list.add_child(kit.para("No saved variants for this chassis yet: refit one in the Mech Lab and use Save variant.", 30, "body500", 1.0, UiStyle.HUD_DIM))
	for o in options:
		var same := Loadout.same(o["parts"], camp.loadout(m)["parts"])
		var q := camp.refit_quote(m, o["parts"], mission)
		var problem := camp.refit_problem(m, o["parts"], mission)
		var sub := "fitted" if same else ("refit %s C%s" % [BayKit.money(int(q["cost"])), (" · " + problem) if problem != "" else ""])
		list.add_child(_overlay_row(String(o["name"]) + ("  (designer)" if o.get("stock", false) else ""), sub, "Apply",
			not same and problem == "", func():
				if o.get("stock", false):
					camp.refit(m, o["parts"], mission)
				else:
					camp.apply_variant(m, o, mission)
				Flow.save_progress()
				_close_overlay()
				_refresh()))
