class_name MissionHud
extends CanvasLayer
## The mission HUD, built in code to Lee's approved mock-up (2026-10-20): framed cyan command
## panels around the battlefield, the MechCommander 2 console's components restyled.
##   top centre    mission bar: mission | current primary objective | done/total, progress
##                 bar and a heading tape (camera yaw)
##   top right     tac map (Minimap) with mission name, mission time and a hint
##   top left      comms (CommsWindow), only while someone talks; objectives under it (O)
##   bottom left   lance: one UnitCard per player unit, compact rows; the selected unit's
##                 card expands. Recent messages sit above it.
##   bottom centre command panel (orders, alpha strike, support powers, Resource Points)
##                 with the rollover help line above it
##   bottom right  systems monitor, only while a unit is selected
## plus the end-of-mission banner and the drag-select box. Sizes are in the base unit
## UiStyle.hud_unit (viewport height / 1080 x the player's HUD scale); the HUD rebuilds
## itself when that changes.
## Dev args (after --): --select=<unit id>[,<id>...] selects units at start, --comms=<unit id> shows
## that unit's pilot talking (screenshots of the expanded card, systems monitor and comms).

const MAX_MESSAGES := 6
const MESSAGE_LIFE := 8.0
const MAX_FORCE := 12  # units in a full force (the original's 3 lances of 4)
const LANCE_EM := 26.0
const MISSION_EM := 54.0
const TAC_EM := 20.0
const OBJECTIVES_EM := 23.5
# Panel anchors, in fractions of the viewport (the mock-up's % offsets).
const EDGE_X := 0.01
const EDGE_TOP := 0.016
const EDGE_BOTTOM := 0.014

var view: Node  # mission_view
var kit: HudKit
var unit_px := 0.0  # the base unit the HUD was built at
var root: Control
var cards: Dictionary = {}  # unit id -> UnitCard
var minimap: Minimap
var mission_panel: PanelContainer
var mission_name: Label
var mission_objective: Label
var mission_count: Label
var mission_bar: HudKit.Bar
var tape: HudKit.Tape
var tac_panel: PanelContainer
var tac_title: Label
var tac_time: Label
var objectives_panel: PanelContainer
var objectives_list: VBoxContainer
var objectives_visible := true
var lance_panel: PanelContainer
var lance_small: Label
var lance_scroll: ScrollContainer
var focus_unit: SimUnit  # the selected unit the systems monitor shows (click a selected card to switch)
const MAX_EXPANDED := 4
var lance_list: VBoxContainer
var log_label: Label
var command_panel: CommandPanel
var help_title: Label
var help_text: Label
var systems: SystemsMonitor
var comms: CommsWindow
var banner: Label
var box: ColorRect
var support_buttons: Dictionary = {}  # power -> CommandPanel.SupportTile
var rp_label: Label
var command_mode := ""  # the armed order (CommandInput.order_mode: jump, guard, run, fire_from_position)
var _placed: Array = []  # [Control, anchor Vector2, grow Vector2i (-1 begin, 0 both, 1 end), offset Vector2]
var _messages: Array = []  # [text, time]
var _map_tex: ImageTexture
var _objectives_sig := ""
var _help_key := ""
var _args := {}


func setup(mission_view: Node) -> void:
	view = mission_view
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	box = ColorRect.new()
	box.color = Color(UiStyle.HUD_EDGE, 0.15)
	box.visible = false
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)
	_build()
	if _args.has("select") or _args.has("comms"):
		_dev_args.call_deferred()


func _viewport_height() -> float:
	var vp := get_viewport()
	return vp.get_visible_rect().size.y if vp else 1080.0


## (Re)build every panel at the current base unit.
func _build() -> void:
	if root:
		remove_child(root)
		root.queue_free()
	_placed.clear()
	cards.clear()
	_objectives_sig = ""
	unit_px = UiStyle.hud_unit(_viewport_height())
	kit = HudKit.new(unit_px)
	root = Control.new()
	root.name = "Hud"
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UiStyle.hud_theme(unit_px)
	add_child(root)
	move_child(root, 0)
	_build_mission_bar()
	_build_tac_map()
	_build_comms_and_objectives()
	_build_lance()
	_build_command()
	systems = SystemsMonitor.new(kit, view.world)
	root.add_child(systems)
	_place(systems, Vector2(1.0 - EDGE_X * 0.8, 1.0 - EDGE_BOTTOM), Vector2i(-1, -1))
	banner = kit.label("", "display700", 4.6, UiStyle.HUD_INK, true, 0.08)
	banner.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	banner.add_theme_constant_override("outline_size", kit.px(0.6))
	banner.visible = false
	root.add_child(banner)
	_place(banner, Vector2(0.5, 0.42), Vector2i(0, 0))
	_layout()


## Keep c at an anchor point of the viewport, growing the given way from it (re-fitted to
## its minimum size every frame, so panels shrink back when content goes).
func _place(c: Control, anchor: Vector2, grow: Vector2i, offset := Vector2.ZERO) -> void:
	c.anchor_left = anchor.x
	c.anchor_right = anchor.x
	c.anchor_top = anchor.y
	c.anchor_bottom = anchor.y
	_placed.append([c, anchor, grow, offset])


func _layout() -> void:
	for p in _placed:
		var c: Control = p[0]
		var s := c.get_combined_minimum_size()
		var g: Vector2i = p[2]
		var o: Vector2 = p[3]
		var x0 := 0.0 if g.x > 0 else (-s.x if g.x < 0 else -s.x / 2.0)
		var y0 := 0.0 if g.y > 0 else (-s.y if g.y < 0 else -s.y / 2.0)
		c.offset_left = roundf(x0 + o.x)
		c.offset_right = roundf(x0 + o.x + s.x)
		c.offset_top = roundf(y0 + o.y)
		c.offset_bottom = roundf(y0 + o.y + s.y)


func _build_mission_bar() -> void:
	var p := kit.panel("", "", MISSION_EM)
	mission_panel = p["panel"]
	root.add_child(mission_panel)
	_place(mission_panel, Vector2(0.5, 0.012), Vector2i(0, 1))
	var m := kit.margin(1.4, 0.5, 1.4, 0.7)
	p["body"].add_child(m)
	var v := kit.vbox(0.5)
	m.add_child(v)
	var line := kit.hbox(0.45)
	line.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(line)
	mission_name = kit.label("", "display600", 1.25, UiStyle.HUD_INK, true, 0.08)
	line.add_child(mission_name)
	line.add_child(kit.label("|", "display600", 1.25, UiStyle.HUD_EDGE))
	mission_objective = kit.label("", "display600", 1.25, UiStyle.HUD_INK, true, 0.08)
	mission_objective.clip_text = true
	mission_objective.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	line.add_child(mission_objective)
	line.add_child(kit.label("|", "display600", 1.25, UiStyle.HUD_EDGE))
	mission_count = kit.label("", "mono", 1.25, UiStyle.HUD_INK)
	line.add_child(mission_count)
	mission_bar = kit.bar(0.35, "edge")
	v.add_child(mission_bar)
	tape = HudKit.Tape.new()
	tape.u = unit_px
	tape.custom_minimum_size = Vector2(0, kit.em(1.6))
	v.add_child(tape)


func _build_tac_map() -> void:
	var p := kit.panel("", "", TAC_EM)
	tac_panel = p["panel"]
	root.add_child(tac_panel)
	_place(tac_panel, Vector2(1.0 - EDGE_X, EDGE_TOP), Vector2i(-1, 1))
	var m := kit.margin(0.6, 0.6, 0.6, 0.5)
	p["body"].add_child(m)
	var v := kit.vbox(0.5)
	m.add_child(v)
	minimap = Minimap.new()
	minimap.ui_unit = unit_px
	minimap.custom_minimum_size = Vector2(kit.em(TAC_EM - 1.2), kit.em(TAC_EM - 1.2))
	v.add_child(minimap)
	minimap.setup(view.world, view.sm.objectives, "res://assets/maps/%s/burnin.jpg" % view.mission, view.sm.player_team, _map_tex)
	_map_tex = minimap.texture()
	minimap.pan_to.connect(_pan_camera)
	minimap.move_to.connect(_on_minimap_move)
	var cap := kit.hbox(0.6)
	v.add_child(cap)
	tac_title = kit.label("", "mono", 1.0, UiStyle.HUD_DIM)
	tac_title.uppercase = true
	tac_title.clip_text = true
	tac_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cap.add_child(tac_title)
	tac_time = kit.label("00:00", "mono", 1.0, UiStyle.HUD_INK)
	cap.add_child(tac_time)
	var hint := kit.label("RMB move", "mono", 1.0, UiStyle.HUD_DIM)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cap.add_child(hint)


func _build_comms_and_objectives() -> void:
	var old := comms
	comms = CommsWindow.new()
	comms.kit = kit
	root.add_child(comms)
	_place(comms, Vector2(EDGE_X, EDGE_TOP), Vector2i(1, 1))
	if old and old.speaker_unit:
		comms.speaker_unit = old.speaker_unit
	var p := kit.panel("Objectives", "O", OBJECTIVES_EM)
	objectives_panel = p["panel"]
	objectives_panel.visible = objectives_visible
	root.add_child(objectives_panel)
	_place(objectives_panel, Vector2(EDGE_X, EDGE_TOP), Vector2i(1, 1), Vector2(0, kit.em(9.6)))
	var m := kit.margin(1.0, 0.5, 1.0, 0.8)
	p["body"].add_child(m)
	objectives_list = kit.vbox(0.35)
	m.add_child(objectives_list)


func _build_lance() -> void:
	var col := kit.vbox(0.6)
	root.add_child(col)
	_place(col, Vector2(EDGE_X * 0.8, 1.0 - EDGE_BOTTOM), Vector2i(1, -1))
	log_label = kit.label("", "body500", 1.05, UiStyle.HUD_INK)
	log_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	log_label.add_theme_constant_override("outline_size", kit.px(0.35))
	log_label.custom_minimum_size.x = kit.em(LANCE_EM)
	log_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	col.add_child(log_label)
	var p := kit.panel("Lance", "", LANCE_EM)
	lance_panel = p["panel"]
	lance_small = p["small"]
	col.add_child(lance_panel)
	var m := kit.margin(0.6, 0.6, 0.6, 0.6)
	p["body"].add_child(m)
	lance_scroll = ScrollContainer.new()
	lance_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	lance_scroll.custom_minimum_size.x = kit.em(LANCE_EM - 1.2)
	m.add_child(lance_scroll)
	lance_list = kit.vbox(0.45)
	lance_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lance_scroll.add_child(lance_list)
	_rebuild_lance()


## The player's force on the GUI, in mission order (at most MAX_FORCE).
func player_units() -> Array:
	var out := []
	for u in view.world.units:
		if u.team == view.sm.player_team and u.is_mover() and u.on_gui and not u.hulk:
			out.append(u)
	return out.slice(0, MAX_FORCE)


func _rebuild_lance() -> void:
	for c in lance_list.get_children():
		lance_list.remove_child(c)
		c.queue_free()
	cards.clear()
	var i := 0
	for u in player_units():
		i += 1
		var n := i
		var c := UnitCard.new(u, kit, n)
		c.force_index = n
		c.picked.connect(_on_card_picked)
		c.ordered.connect(_on_card_order)
		c.focus_requested.connect(_focus_unit)
		c.hover_help = _hover
		lance_list.add_child(c)
		cards[u.id] = c


func _build_command() -> void:
	var col := kit.vbox(0.9)
	root.add_child(col)
	_place(col, Vector2(0.5, 1.0 - EDGE_BOTTOM), Vector2i(0, -1))
	var help := kit.hbox(0.5)
	help.alignment = BoxContainer.ALIGNMENT_CENTER
	help.custom_minimum_size = Vector2(kit.em(CommandPanel.WIDTH_EM), kit.em(1.6))
	col.add_child(help)
	help_title = kit.label("", "display600", 1.1, UiStyle.HUD_EDGE, true, 0.08)
	help_text = kit.label("", "body400", 1.1, UiStyle.HUD_INK)
	for l in [help_title, help_text]:
		l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.7))
		l.add_theme_constant_override("outline_size", kit.px(0.35))
		help.add_child(l)
	command_panel = CommandPanel.new(kit, view.sm.support != null)
	command_panel.command.connect(_on_command)
	command_panel.support.connect(_on_support)
	command_panel.hover_help = _hover
	col.add_child(command_panel)
	support_buttons = command_panel.tiles
	rp_label = command_panel.rp_label
	_hover(_help_key)


## The rollover help line: title and description of the hovered control ("" clears it).
func _hover(key: String) -> void:
	_help_key = key
	var h := CommandPanel.help_for(key)
	help_title.text = h[0] if h.size() > 0 else ""
	help_text.text = h[1] if h.size() > 1 else ""


## A command from the panel or a card. Stop and hold act on the selection at once; alpha
## strike toggles; run, jump, guard and fire-from-position toggle a mode CommandInput applies
## to the next right-click (ControlGui::handleClick, controlGui.cpp:1560-1595).
func _on_command(kind: String) -> void:
	match kind:
		"stop":
			view.input.stop()
		"hold":
			view.input.toggle_hold_position()
		"alpha_strike":
			view.input.toggle_alpha_strike()
		_:
			view.input.toggle_mode(kind)
	command_mode = view.input.order_mode


func _on_card_order(u: SimUnit, kind: String) -> void:
	if not view.input.selection.has(u):
		view.input._set_selection([u])
	_on_command(kind)


func _on_support(kind: String) -> void:
	view.input.support_kind = kind if view.input.support_kind != kind else ""


func _on_card_picked(u: SimUnit, add: bool) -> void:
	if not add and view.input.selection.size() > 1 and view.input.selection.has(u):
		focus_unit = u  # a card in a selected group: show it in the systems monitor, keep the group selected
		return
	focus_unit = u
	var s: Array = view.input.selection.duplicate() if add else []
	if not s.has(u):
		s.append(u)
	view.input._set_selection(s)


## Double-click on a card: the camera follows the unit until the player pans (RtsCamera.follow).
func _focus_unit(u: SimUnit) -> void:
	view.camera.follow(u)


## Minimap pan: RtsCamera.pan_to clamps to the map and stops any follow.
func _pan_camera(p: Vector2) -> void:
	view.camera.pan_to(p)


func _on_minimap_move(p: Vector2) -> void:
	for m in view.input.selection:
		view.world.order_move(m, p)


## A pilot talking: the comms panel shows their portrait and line, and their card blinks.
func pilot_says(u: SimUnit, text: String, seconds := -1.0) -> void:
	var who := "%s · %s" % [u.pilot.name if u.pilot else u.name, u.name]
	comms.say(who, text, u, seconds)


func _dev_args() -> void:
	if _args.has("select"):  # one id or a comma list
		var pick: Array = []
		for t in String(_args["select"]).split(","):
			var id := int(t)
			if id >= 0 and id < view.world.units.size():
				pick.append(view.world.units[id])
		view.input._set_selection(pick)
	if _args.has("comms"):
		var id := int(_args["comms"])
		if id >= 0 and id < view.world.units.size():
			pilot_says(view.world.units[id], "Airfield in sight. Picking up a 'Mech on the apron, looks like a Starslayer.", 600.0)


func message(text: String) -> void:
	_messages.append([text, view.world.time])
	if _messages.size() > MAX_MESSAGES:
		_messages.pop_front()


func on_event(e: Dictionary) -> void:
	var w: SimWorld = view.world
	match e["type"]:
		"objective":
			if not e["hidden"]:
				message("Objective complete: " + _objective_title(view.sm.objectives.objectives[e["index"]]))
		"disabled":
			var u: SimUnit = w.units[e["unit"]]
			if u.team == view.sm.player_team and u.is_mover() and u.on_gui:
				message("%s is down!" % u.name)
			elif u.is_mover():
				message("%s destroyed" % u.name)
			elif u is SimStructure:
				message("%s destroyed" % u.name)
		"fell":
			var u: SimUnit = w.units[e["unit"]]
			if u.team == view.sm.player_team:
				message("%s has fallen" % u.name)
		"objective_failed":
			if not e["hidden"]:
				message("Objective failed: " + _objective_title(view.sm.objectives.objectives[e["index"]]))
		"captured":
			message("%s captured %s" % [w.units[e["unit"]].name, w.units[e["target"]].name])
		"resource_points":
			message("+%d Resource Points" % int(e["amount"]))
		"support":
			if e.get("enemy", false):
				message("Incoming enemy air strike!")
			else:
				message("%s on the way" % SimSupport.LABELS.get(e["kind"], e["kind"]))
		"support_refused":
			message("Can't call %s there" % SimSupport.LABELS.get(e["kind"], "support").to_lower())
		"repair_done":
			message("%s repaired" % w.units[e["unit"]].name)
		"salvaged", "unit_added":
			var u: SimUnit = w.units[e["unit"]]
			message("%s joins your force" % u.name)
			if u.team == view.sm.player_team and u.on_gui and not cards.has(u.id):
				_rebuild_lance()
		"capture_refused", "capture_blocked":
			message("%s cannot capture %s%s" % [w.units[e["unit"]].name, w.units[e["target"]].name,
				" — enemy nearby" if e["type"] == "capture_blocked" else ""])


func _objective_title(obj: Dictionary) -> String:
	var t: String = GameData.string(obj["title_string"]) if obj["title_string"] > 0 else ""
	return UiStyle.objective_title(t if not t.is_empty() else String(obj["title"]))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_O:
		objectives_visible = not objectives_visible
		objectives_panel.visible = objectives_visible
		get_viewport().set_input_as_handled()


func _process(_delta: float) -> void:
	if absf(UiStyle.hud_unit(_viewport_height()) - unit_px) > 0.01:
		_build()  # viewport height or HUD scale changed
	var w: SimWorld = view.world
	var sel: Array = view.input.selection
	var first: SimUnit = focus_unit if sel.has(focus_unit) else (sel[0] if not sel.is_empty() else null)
	_update_mission(w)
	_update_objectives()
	tac_title.text = view.title if not String(view.title).is_empty() else view.mission
	tac_time.text = "%02d:%02d" % [int(w.time) / 60, int(w.time) % 60]
	minimap.view_polygon = _camera_footprint()
	# messages
	var keep := []
	for m in _messages:
		if w.time - m[1] < MESSAGE_LIFE:
			keep.append(m)
	_messages = keep
	log_label.text = "\n".join(_messages.map(func(m): return m[0]))
	# lance
	command_mode = view.input.order_mode
	var modes := {}
	for k in ["run", "jump", "guard", "fire_from_position", "hold"]:
		modes[k] = view.input.mode_on(k)
	modes["alpha_strike"] = not sel.is_empty() and sel.all(func(m): return m.ignore_heat_discipline)
	var tons := 0.0
	var expanded_n := 0
	for id in cards:
		var c: UnitCard = cards[id]
		var u: SimUnit = w.units[id]
		tons += u.tonnage
		c.selected = sel.has(u)
		# every selected unit gets its full card, up to MAX_EXPANDED; past that, highlighted compact rows
		c.expanded = c.selected and expanded_n < MAX_EXPANDED
		if c.expanded:
			expanded_n += 1
		c.speaking = comms.visible and comms.speaker_unit == u
		c.active_modes = modes if c.selected else {}
		# the card's number: its lowest selection group (Ctrl+n, CommandInput), else its force position
		var gs: Array = view.input.groups_of(u)
		c.group = gs.min() if not gs.is_empty() and gs.min() > 0 else c.force_index
	lance_small.text = "%d t · %d / %d" % [roundi(tons), cards.size(), MAX_FORCE]
	lance_scroll.custom_minimum_size.y = minf(lance_list.get_combined_minimum_size().y, _viewport_height() * 0.52)
	# command panel, systems, comms
	command_panel.update_state(modes, view.sm.support, view.input.support_kind, view.input.can_jump())
	systems.show_unit(first)
	comms.set_voice(view.audio != null and view.audio.voice != null and view.audio.voice.playing)
	_update_banner()
	_layout()


func _update_mission(w: SimWorld) -> void:
	var objs: Array = view.sm.objectives.visible_objectives()
	var done := objs.filter(func(o): return o["complete"]).size()
	var current := ""
	for o in objs:
		if o["primary"] and not o["complete"] and not o["failed"]:
			current = _objective_title(o)
			break
	if current.is_empty():
		current = "All objectives complete" if done == objs.size() and not objs.is_empty() else "—"
	mission_name.text = view.title if not String(view.title).is_empty() else view.mission
	mission_objective.text = current
	var f := UiStyle.font("display600", roundi(0.08 * 1.25 * unit_px))
	var want := f.get_string_size(current.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, kit.px(1.25)).x + 2.0
	mission_objective.custom_minimum_size.x = minf(want, kit.em(MISSION_EM - 2.8) - mission_name.get_minimum_size().x - mission_count.get_minimum_size().x - kit.em(3.0))
	mission_count.text = "%d / %d" % [done, objs.size()]
	mission_bar.value = float(done) / maxf(objs.size(), 1.0)
	tape.heading = fposmod(view.camera.yaw_deg, 360.0)


func _update_objectives() -> void:
	var objs: Array = view.sm.objectives.visible_objectives()
	var sig := ",".join(objs.map(func(o): return "%d%s%s" % [o["index"], o["complete"], o["failed"]]))
	if sig == _objectives_sig:
		return
	_objectives_sig = sig
	for c in objectives_list.get_children():
		objectives_list.remove_child(c)
		c.queue_free()
	var secondary := objs.filter(func(o): return not o["primary"])
	for o in objs.filter(func(o): return o["primary"]):
		objectives_list.add_child(_objective_row(o))
	if not secondary.is_empty():
		var sec := kit.label("Secondary", "display600", 0.8, UiStyle.HUD_DIM, true, 0.14)
		objectives_list.add_child(sec)
		for o in secondary:
			objectives_list.add_child(_objective_row(o))


func _objective_row(o: Dictionary) -> HBoxContainer:
	var row := kit.hbox(0.5)
	var b := ObjectiveBox.new()
	b.state = 1 if o["complete"] else (2 if o["failed"] else 0)
	b.custom_minimum_size = Vector2(kit.em(1.05), kit.em(1.05))
	b.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(b)
	var t := kit.para(_objective_title(o), OBJECTIVES_EM - 2.0 - 1.6, "body400", 1.1,
		UiStyle.HUD_DIM if o["complete"] or o["failed"] else UiStyle.HUD_INK)
	row.add_child(t)
	return row


func _update_banner() -> void:
	var res: int = view.sm.objectives.result
	if view.pause_menu and view.pause_menu.ended:
		banner.visible = false  # the end panel takes over
	elif res != SimObjectives.Result.PLAYING and not banner.visible:
		banner.visible = true
		banner.text = "Mission successful" if res == SimObjectives.Result.WON else "Mission failed"
		banner.add_theme_color_override("font_color", UiStyle.HUD_OK if res == SimObjectives.Result.WON else UiStyle.HUD_CRIT)


## Fraction of the viewport covered by visible HUD panels (the mock-up's coverage meter:
## union of panel rects on a 4 px grid).
func coverage() -> float:
	var vs := get_viewport().get_visible_rect().size
	var gw := int(ceil(vs.x / 4.0))
	var gh := int(ceil(vs.y / 4.0))
	var grid := PackedByteArray()
	grid.resize(gw * gh)
	for c in [mission_panel, tac_panel, comms, objectives_panel, lance_panel, command_panel, systems]:
		if c == null or not c.is_visible_in_tree():
			continue
		var r: Rect2 = c.get_global_rect()
		var x0 := clampi(int(floor(r.position.x / 4.0)), 0, gw)
		var x1 := clampi(int(ceil(r.end.x / 4.0)), 0, gw)
		for y in range(clampi(int(floor(r.position.y / 4.0)), 0, gh), clampi(int(ceil(r.end.y / 4.0)), 0, gh)):
			for x in range(x0, x1):
				grid[y * gw + x] = 1
	var n := 0
	for v in grid:
		n += v
	return float(n) / maxf(grid.size(), 1.0)


## World positions of the four screen corners on the ground (water plane fallback).
func _camera_footprint() -> PackedVector2Array:
	var out := PackedVector2Array()
	var cam: Camera3D = view.camera
	var vs := get_viewport().get_visible_rect().size
	for corner in [Vector2.ZERO, Vector2(vs.x, 0), vs, Vector2(0, vs.y)]:
		var g = view.input.ground_at(corner)
		if g == null:
			var o := cam.project_ray_origin(corner)
			var d := cam.project_ray_normal(corner)
			var water: float = view.world.map.water_level_m
			var t: float = (water - o.y) / d.y if absf(d.y) > 0.001 else 3000.0
			t = clampf(t, 0.0, 3000.0)
			var p := o + d * t
			g = Vector2(p.x, -p.z)
		out.append(g)
	return out


## An objective's checkbox: cyan square, green with a tick when done, red cross when failed.
class ObjectiveBox:
	extends Control
	var state := 0  # 0 open, 1 done, 2 failed

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var s := minf(size.x, size.y) * 0.86
		var r := Rect2(Vector2(0, (size.y - s) * 0.5 + s * 0.12), Vector2(s, s))
		var col := UiStyle.HUD_OK if state == 1 else (UiStyle.HUD_CRIT if state == 2 else UiStyle.HUD_EDGE)
		draw_rect(r, col, false, 1.0)
		var w := maxf(1.5, s / 7.0)
		if state == 1:
			draw_polyline(PackedVector2Array([r.position + r.size * Vector2(0.2, 0.52), r.position + r.size * Vector2(0.42, 0.74),
				r.position + r.size * Vector2(0.8, 0.28)]), col, w, true)
		elif state == 2:
			draw_line(r.position + r.size * 0.25, r.position + r.size * 0.75, col, w, true)
			draw_line(r.position + r.size * Vector2(0.75, 0.25), r.position + r.size * Vector2(0.25, 0.75), col, w, true)
