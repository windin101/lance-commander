extends Control
## Mech Bay (campaign-layer.md 3): deploy 'Mechs from the inventory within the drop
## weight and the 12-slot cap, assign pilots (Pilot Ready), sell reserve 'Mechs, buy
## from the mission's purchase list; Launch when every deployed 'Mech has a pilot.

var mission := ""
var camp: Campaign
var _body: HBoxContainer
var _status: Label
var _launch: Button


func _ready() -> void:
	theme = UiStyle.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiStyle.backdrop(self)
	mission = Flow.current
	camp = Flow.campaign
	if OS.get_cmdline_user_args().has("--sample-campaign"):  # dev: screenshot without playing mc2_01
		mission = "mc2_02"
		camp.reset()
		camp.add_mech("werewolf", 0, "pmwflash", 1)
		camp.add_mech("bushwacker", 0, "pmwhacksaw", 2)
		camp.add_mech("bushwacker", 0, "", 0)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 28)
	add_child(margin)
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 14)
	margin.add_child(page)
	var head := VBoxContainer.new()
	head.add_theme_constant_override("separation", 2)
	head.add_child(UiStyle.label("Mech Bay · %s" % MissionBrief.load_mission(GameData, mission).title, 13, UiStyle.DIM, true))
	_status = UiStyle.label("", 26, UiStyle.TEXT, true)
	head.add_child(_status)
	page.add_child(head)
	_body = HBoxContainer.new()
	_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_body.add_theme_constant_override("separation", 18)
	page.add_child(_body)
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 12)
	var back := Button.new()
	back.text = "Back to briefing"
	back.pressed.connect(func(): Flow.goto_briefing(mission))
	foot.add_child(back)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foot.add_child(spacer)
	_launch = Button.new()
	_launch.text = "Launch mission"
	_launch.add_theme_font_size_override("font_size", 20)
	_launch.pressed.connect(func():
		Flow.save_progress()
		Flow.launch())
	foot.add_child(_launch)
	page.add_child(foot)
	_refresh()


func _refresh() -> void:
	for c in _body.get_children():
		c.queue_free()
	_body.add_child(_inventory_panel())
	if bool(camp.mission_info(mission).get("PlayPurchasing", true)):
		_body.add_child(_purchase_panel())
	var problem := camp.launch_problem(mission)
	_status.text = "C-Bills %s   ·   drop weight %d / %d t   ·   %d / %d deployed" % [_money(camp.c_bills),
		int(camp.deployed_tonnage()), int(camp.drop_limit(mission)), camp.deployed().size(), Campaign.MAX_DEPLOY]
	_launch.disabled = problem != ""
	_launch.tooltip_text = problem
	_launch.text = "Launch mission" if problem == "" else problem


static func _money(v: int) -> String:
	var s := str(absi(v))
	var out := ""
	while s.length() > 3:
		out = "," + s.right(3) + out
		s = s.left(s.length() - 3)
	return ("-" if v < 0 else "") + s + out


func _column(title: String) -> Array:
	var p := PanelContainer.new()
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 8)
	p.add_child(outer)
	outer.add_child(UiStyle.heading(title))
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	outer.add_child(scroll)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 8)
	scroll.add_child(v)
	return [p, v]


func _inventory_panel() -> Control:
	var col := _column("Your 'Mechs")
	var list: VBoxContainer = col[1]
	var mechs := camp.mechs.duplicate()
	mechs.sort_custom(func(a, b): return (a["slot"] if a["slot"] > 0 else 99) < (b["slot"] if b["slot"] > 0 else 99))
	for m in mechs:
		list.add_child(_mech_row(m))
	if mechs.is_empty():
		list.add_child(UiStyle.label("No 'Mechs. Buy some from the purchase list.", 15, UiStyle.WARN))
	return col[0]


func _mech_row(m: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.add_theme_constant_override("separation", 0)
	var v := camp.variant(m["chassis"], int(m["variant"]))
	var deployed := int(m["slot"]) > 0
	info.add_child(UiStyle.label("%s%s" % ["%d · " % int(m["slot"]) if deployed else "", String(v.get("name", m["chassis"]))],
		16, UiStyle.ACCENT if deployed else UiStyle.TEXT))
	info.add_child(UiStyle.label("%d t · %s C-Bills" % [int(camp.tonnage(m["chassis"])), _money(camp.price(m["chassis"], int(m["variant"])))],
		13, UiStyle.DIM))
	row.add_child(info)
	if deployed:
		var pick := OptionButton.new()
		pick.custom_minimum_size = Vector2(230, 0)
		var options: Array[String] = [""]
		if String(m["pilot"]) != "":
			options.append(String(m["pilot"]))
		for p in camp.free_pilots(mission):
			if not options.has(p):
				options.append(p)
		for p in options:
			pick.add_item(_pilot_text(p) if p != "" else "— pilot —")
			if p == String(m["pilot"]):
				pick.select(pick.item_count - 1)
		pick.item_selected.connect(func(i):
			m["pilot"] = options[i]
			_refresh())
		row.add_child(pick)
		var out := Button.new()
		out.text = "Withdraw"
		out.pressed.connect(func():
			camp.withdraw(m)
			_refresh())
		row.add_child(out)
	else:
		var add := Button.new()
		add.text = "Deploy"
		add.disabled = not camp.can_deploy(m, mission)
		add.pressed.connect(func():
			camp.deploy(m, mission)
			_refresh())
		row.add_child(add)
		if bool(camp.mission_info(mission).get("PlayPurchasing", true)):
			var sell := Button.new()
			sell.text = "Sell"
			sell.pressed.connect(func():
				camp.sell(m)
				_refresh())
			row.add_child(sell)
	return row


func _pilot_text(p: String) -> String:
	var d: Dictionary = camp.pilots.get(p, {})
	return "%s · %s · G%d P%d" % [d.get("name", p), Campaign.rank(d), int(d.get("gunnery", 0)), int(d.get("piloting", 0))]


func _purchase_panel() -> Control:
	var col := _column("Purchase")
	var list: VBoxContainer = col[1]
	for o in camp.purchasable(mission):
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 10)
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		info.add_theme_constant_override("separation", 0)
		info.add_child(UiStyle.label(String(o["name"]), 16))
		info.add_child(UiStyle.label("%d t · %s C-Bills" % [int(o["tonnage"]), _money(int(o["price"]))], 13, UiStyle.DIM))
		row.add_child(info)
		var buy := Button.new()
		buy.text = "Buy"
		buy.disabled = int(o["price"]) > camp.c_bills
		buy.pressed.connect(func():
			camp.buy(String(o["chassis"]), int(o["variant"]))
			_refresh())
		row.add_child(buy)
		list.add_child(row)
	return col[0]
