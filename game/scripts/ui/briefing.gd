class_name BriefingScreen
extends Control
## Mission briefing, in the HUD style of the bay, lab, market and pilots screens (a
## MechWarrior 5-like contract briefing over the original's MissionBriefingScreen):
##   top      operation, mission and its place in the campaign; drop weight limit,
##            support RP, C-Bills
##   left     objectives, primary then secondary: number, title, description, reward
##            (C-Bills on success); the lance going in
##   centre   the tactical map: terrain, drop zone, numbered objective markers, legend
##   right    the target view (the objective's model, as the original's briefing camera;
##            the operation's briefing video plays there first when converted), the
##            briefing text with the Tactical Officer's notes, and intel (support powers
##            enabled, weather, time limit)
##   bottom   New campaign, Previous mission; Mech Bay (missions with logistics) and Launch
## As the original, the objectives cycle every 3 s until the player picks one; picking a
## list row or a map marker selects it. Enter does what the main button does.
## Dev: --sample-campaign fills the campaign with mission 2's lance; --mission=mc2_NN.

const CYCLE_S := 3.0

var brief: MissionBrief
var kit: BayKit
var launch_button: Button
var bay_button: Button
var launch_note: Label
var music: AudioStreamPlayer
var map: BriefingMap
var target: MechStage
var target_label: Label
var video: VideoStreamPlayer
var numbered: Array = []  # [[number, objective]], primaries first
var selected := -1  # number of the selected objective
var user_picked := false
var _rows := {}  # number -> PanelContainer
var _cycle_t := 0.0


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	for arg in OS.get_cmdline_user_args():  # dev: --sample-campaign [--mission=mc2_NN] for screenshots
		if arg == "--sample-campaign":
			Flow.current = MechBay.dev_sample(Flow.campaign)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mission="):
			Flow.current = arg.trim_prefix("--mission=")
	var mission: String = Flow.current
	brief = MissionBrief.load_mission(GameData, mission)
	var vh := get_viewport().get_visible_rect().size.y if get_viewport() else 1080.0
	kit = BayKit.new(UiStyle.hud_unit(vh))
	theme = UiStyle.hud_theme(kit.u)
	var bg := ColorRect.new()
	bg.color = Color("#0b141b")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var back := BayKit.Backdrop.new()
	back.gantries = false
	add_child(back)
	var n := 0
	for primary in [true, false]:
		for o in brief.visible_objectives():
			if bool(o["primary"]) == primary:
				n += 1
				numbered.append([n, o])
	_top_bar(mission)
	_objectives_panel()
	_map_panel()
	_briefing_panel()
	_footer()
	_play_tune(int(Flow.info(mission).get("tune", -1)))
	_start_video(String(Flow.info(mission).get("video", "")))
	if not numbered.is_empty():
		select_objective(1, false)


func _logistics() -> bool:
	return Flow.uses_logistics(brief.mission)


# --- layout ------------------------------------------------------------------------------

func _top_bar(mission: String) -> void:
	var top := PanelContainer.new()
	top.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	kit.place(top, 0.01, 0.016, 0.99, 0.016)
	add_child(top)
	var tm := kit.margin(1.4, 0.7, 1.4, 0.7)
	top.add_child(tm)
	var th := kit.hbox(2.4)
	tm.add_child(th)
	var title := kit.vbox(0.15)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var idx := Flow.index_of(mission)
	title.add_child(kit.label("Mission briefing · operation %d · mission %d of %d" % [int(Flow.info(mission).get("group", 0)) + 1,
		idx + 1, Flow.missions.size()], "display500", 0.9, UiStyle.HUD_DIM, true, 0.1))
	title.add_child(kit.label(brief.title, "display700", 1.7, UiStyle.HUD_INK, true, 0.1))
	th.add_child(title)
	if brief.available:
		var drop := kit.fig("Drop weight limit")
		drop["value"].text = "%d t" % int(brief.drop_limit)
		th.add_child(drop["box"])
		var rp := kit.fig("Support")
		rp["value"].text = "%s RP" % BayKit.money(brief.support_rp)
		th.add_child(rp["box"])
	if Flow.campaign:
		var cash := kit.fig("C-Bills")
		cash["value"].text = BayKit.money(Flow.campaign.c_bills)
		th.add_child(cash["box"])


func _objectives_panel() -> void:
	var p := kit.panel("Objectives", "")
	var n_primary := numbered.filter(func(e): return e[1]["primary"]).size()
	p["small"].text = "%d primary · %d secondary" % [n_primary, numbered.size() - n_primary]
	kit.place(p["panel"], 0.01, 0.13, 0.01, 0.905, 30.0)
	add_child(p["panel"])
	var sc := ScrollContainer.new()
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	p["body"].add_child(sc)
	var mm := kit.margin(0.6, 0.6, 0.6, 0.6)
	mm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sc.add_child(mm)
	var list := kit.vbox(0.4)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mm.add_child(list)
	var section := ""
	for e in numbered:
		var o: Dictionary = e[1]
		var s := "Primary" if o["primary"] else "Secondary"
		if s != section:
			section = s
			list.add_child(kit.label(s, "display600", 0.85, UiStyle.HUD_EDGE, true, 0.12))
		list.add_child(_objective_row(int(e[0]), o))
	if numbered.is_empty():
		list.add_child(kit.label("No objectives." if brief.available else "Not yet available.", "body400", 1.0, UiStyle.HUD_DIM))
	# the lance going in
	p["body"].add_child(kit.rule())
	var lm := kit.margin(0.9, 0.6, 0.9, 0.7)
	p["body"].add_child(lm)
	var lv := kit.vbox(0.3)
	lm.add_child(lv)
	lv.add_child(kit.label("Your lance" + (" · from the Mech Bay" if _logistics() else ""), "display600", 0.85, UiStyle.HUD_EDGE, true, 0.12))
	for row in _lance():
		var h := kit.hbox(0.6)
		var a := kit.label(row[0], "body500", 1.0, UiStyle.HUD_INK)
		a.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		a.clip_text = true
		h.add_child(a)
		h.add_child(kit.label(row[1], "mono", 0.85, UiStyle.HUD_DIM))
		lv.add_child(h)


## [[chassis and variant, "tons · pilot"]]: the campaign's deployed force when logistics
## replaces the mission's lance (3.4), else the mission's own player parts.
func _lance() -> Array:
	var out := []
	if _logistics():
		for m in Flow.campaign.deployed():
			var cn := String(GameData.chassis.get(String(m["chassis"]), {}).get("name", m["chassis"]))
			var who := String(Flow.campaign.pilots.get(String(m["pilot"]), {}).get("name", "no pilot")) if String(m["pilot"]) != "" else "no pilot"
			var vn := String(Flow.campaign.loadout(m)["name"])
			out.append(["%s · %s" % [cn, vn.substr(cn.length()).strip_edges() if vn.begins_with(cn) and vn.length() > cn.length() else vn],
				"%d t · %s" % [int(Flow.campaign.tonnage(m["chassis"])), who]])
		if out.is_empty():
			out.append(["None deployed yet", "pick a force in the Mech Bay"])
		return out
	for m in brief.lance:
		var who := String(m["pilot"])
		if m["callsign"] != "" and String(m["callsign"]).to_lower() != who.to_lower():
			who += " \"%s\"" % m["callsign"]
		out.append(["%s  %s" % [m["chassis"], m["variant"]], "%d t · %s" % [int(m["tonnage"]), who]])
	return out


func _objective_row(n: int, o: Dictionary) -> Control:
	var row := PanelContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_STOP
	row.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row.gui_input.connect(func(ev):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			select_objective(n, true))
	_rows[n] = row
	var h := kit.hbox(0.6)
	row.add_child(h)
	var col: Color = UiStyle.HUD_OK if o["primary"] else UiStyle.HUD_WARN
	var badge := PanelContainer.new()
	var bs := StyleBoxFlat.new()
	bs.bg_color = col
	bs.content_margin_left = kit.em(0.35)
	bs.content_margin_right = kit.em(0.35)
	badge.add_theme_stylebox_override("panel", bs)
	badge.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var bl := kit.label(str(n), "display700", 0.95, BayKit.DARK_TEXT)
	bl.custom_minimum_size = Vector2(kit.em(1.1), kit.em(1.3))
	bl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	bl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	badge.add_child(bl)
	h.add_child(badge)
	var v := kit.vbox(0.15)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var title := UiStyle.objective_title(String(o["title"]))
	var t := kit.label(title, "body600", 1.05, UiStyle.HUD_INK)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(t)
	var desc := UiStyle.objective_title(String(o.get("description", "")))
	if desc != "" and desc != title:
		var d := kit.label(desc, "body400", 0.95, UiStyle.HUD_DIM)
		d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		v.add_child(d)
	var meta := []
	if int(o.get("reward", 0)) > 0:
		meta.append("Reward %s C" % BayKit.money(int(o["reward"])))
	if o["marker"] == null:
		meta.append("no map marker")
	if not meta.is_empty():
		v.add_child(kit.label("  ·  ".join(meta), "mono", 0.85, UiStyle.HUD_EDGE if int(o.get("reward", 0)) > 0 else UiStyle.HUD_DIM))
	h.add_child(v)
	_style_row(n)
	return row


func _style_row(n: int) -> void:
	var row: PanelContainer = _rows.get(n)
	if row == null:
		return
	var sel := n == selected
	var s := StyleBoxFlat.new()
	s.bg_color = UiStyle.HUD_PANEL_2.lerp(UiStyle.HUD_EDGE, 0.12) if sel else Color(UiStyle.HUD_PANEL_2, 0.6)
	s.border_color = UiStyle.HUD_EDGE if sel else Color(UiStyle.HUD_EDGE, 0.15)
	s.set_border_width_all(1)
	s.content_margin_left = kit.em(0.6)
	s.content_margin_right = kit.em(0.6)
	s.content_margin_top = kit.em(0.45)
	s.content_margin_bottom = kit.em(0.45)
	row.add_theme_stylebox_override("panel", s)


func _map_panel() -> void:
	var p := kit.panel("Tactical map", ("%.1f km across" % (brief.map_half_m * 2.0 / 1000.0)) if brief.map_half_m > 0.0 else "")
	kit.place(p["panel"], 0.205, 0.13, 0.795, 0.905)
	p["panel"].offset_left = kit.em(0.6)
	p["panel"].offset_right = -kit.em(0.6)
	add_child(p["panel"])
	var mm := kit.margin(0.8, 0.8, 0.8, 0.6)
	mm.size_flags_vertical = Control.SIZE_EXPAND_FILL
	p["body"].add_child(mm)
	map = BriefingMap.new()
	map.brief = brief
	map.u = kit.u
	map.numbered = numbered
	map.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map.picked.connect(func(n): select_objective(n, true))
	mm.add_child(map)
	p["body"].add_child(kit.rule())
	var lm := kit.margin(1.0, 0.5, 1.0, 0.5)
	p["body"].add_child(lm)
	var legend := kit.hbox(1.6)
	legend.alignment = BoxContainer.ALIGNMENT_CENTER
	lm.add_child(legend)
	for item in [["Primary objective", UiStyle.HUD_OK, "o"], ["Secondary objective", UiStyle.HUD_WARN, "o"], ["Drop zone", UiStyle.HUD_EDGE, "d"]]:
		var h := kit.hbox(0.4)
		var sw := Legend.new()
		sw.colour = item[1]
		sw.shape = item[2]
		sw.custom_minimum_size = Vector2(kit.em(1.1), kit.em(1.1))
		sw.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(sw)
		h.add_child(kit.label(item[0], "display600", 0.85, UiStyle.HUD_DIM, true, 0.1))
		legend.add_child(h)


func _briefing_panel() -> void:
	var p := kit.panel("Briefing", "")
	kit.place(p["panel"], 0.99, 0.13, 0.99, 0.905, 32.0, true)
	add_child(p["panel"])
	# the target view
	var slot := Control.new()
	slot.custom_minimum_size = Vector2(0, kit.em(15.0))
	slot.clip_contents = true
	p["body"].add_child(slot)
	var glow := ColorRect.new()
	glow.color = Color(UiStyle.HUD_EDGE, 0.05)
	glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(glow)
	target = MechStage.new()
	target.set_anchors_preset(Control.PRESET_FULL_RECT)
	target.spin = 14.0
	slot.add_child(target)
	target_label = kit.label("", "display600", 0.85, UiStyle.HUD_EDGE, true, 0.12)
	target_label.position = Vector2(kit.em(0.9), kit.em(0.5))
	slot.add_child(target_label)
	video = VideoStreamPlayer.new()
	video.set_anchors_preset(Control.PRESET_FULL_RECT)
	video.expand = true
	video.visible = false
	video.finished.connect(func():
		video.visible = false
		target.visible = true)
	slot.add_child(video)
	p["body"].add_child(kit.rule())
	# the text
	var tm := kit.margin(1.0, 0.7, 0.6, 0.5)
	tm.size_flags_vertical = Control.SIZE_EXPAND_FILL
	p["body"].add_child(tm)
	var rt := RichTextLabel.new()
	rt.bbcode_enabled = true
	rt.scroll_active = true
	rt.size_flags_vertical = Control.SIZE_EXPAND_FILL
	rt.add_theme_font_override("normal_font", UiStyle.font("body400"))
	rt.add_theme_font_override("bold_font", UiStyle.font("display600", kit.px(0.1)))
	rt.add_theme_font_size_override("normal_font_size", kit.px(1.1))
	rt.add_theme_font_size_override("bold_font_size", kit.px(0.95))
	rt.add_theme_color_override("default_color", UiStyle.HUD_INK)
	rt.add_theme_constant_override("line_separation", kit.px(0.2))
	var text := ""
	if not brief.available:
		text = "[color=#%s]This mission's data is not converted yet. It arrives in a later build.[/color]" % UiStyle.HUD_WARN.to_html(false)
	else:
		if brief.summary != "":
			text += "[color=#%s]%s[/color]\n\n" % [UiStyle.HUD_DIM.to_html(false), brief.summary.replace("[", "[lb]")]
		text += _briefing_bbcode(brief.blurb)
	rt.text = text
	tm.add_child(rt)
	# intel
	if brief.available:
		p["body"].add_child(kit.rule())
		var im := kit.margin(1.0, 0.6, 1.0, 0.7)
		p["body"].add_child(im)
		var g := GridContainer.new()
		g.columns = 2
		g.add_theme_constant_override("h_separation", kit.px(0.8))
		g.add_theme_constant_override("v_separation", kit.px(0.25))
		im.add_child(g)
		var rows := [["Drop weight", "%d t" % int(brief.drop_limit)], ["Support budget", "%s RP" % BayKit.money(brief.support_rp)],
			["Support", ", ".join(brief.support) if not brief.support.is_empty() else "none"], ["Weather", brief.weather()]]
		if brief.time_limit > 0.0:
			rows.append(["Time limit", "%d min" % roundi(brief.time_limit / 60.0)])
		for r in rows:
			var k := kit.label(r[0], "display600", 0.85, UiStyle.HUD_DIM, true, 0.1)
			k.custom_minimum_size.x = kit.em(8.5)
			k.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
			g.add_child(k)
			var v := kit.label(r[1], "body500", 1.0, UiStyle.HUD_INK)
			v.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			g.add_child(v)


## The blurb's "Tactical Officer Notes:" section gets its own accent heading.
static func _briefing_bbcode(text: String) -> String:
	var esc := text.strip_edges().replace("[", "[lb]")
	var marker := "Tactical Officer Notes:"
	var at := esc.find(marker)
	if at < 0:
		return esc
	return esc.substr(0, at).strip_edges() + "\n\n[color=#%s][b]TACTICAL OFFICER NOTES[/b][/color]\n" % UiStyle.HUD_EDGE.to_html(false) \
		+ esc.substr(at + marker.length()).strip_edges()


func _footer() -> void:
	var bar := PanelContainer.new()
	bar.add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	kit.place(bar, 0.01, 0.984, 0.99, 0.984)
	bar.grow_vertical = Control.GROW_DIRECTION_BEGIN
	add_child(bar)
	var bm := kit.margin(1.0, 0.6, 1.0, 0.6)
	bar.add_child(bm)
	var h := kit.hbox(0.8)
	bm.add_child(h)
	h.add_child(kit.button("New campaign", func():
		Flow.new_campaign()
		Flow.goto_briefing()))
	if Flow.index_of(brief.mission) > 0:
		h.add_child(kit.button("Previous mission", func(): Flow.goto_briefing(Flow.missions[Flow.index_of(brief.mission) - 1]["name"])))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(spacer)
	launch_note = kit.label("", "body500", 0.95, UiStyle.HUD_WARN)
	launch_note.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(launch_note)
	if _logistics():
		# Mech Bay (the original's Next), and Launch straight away when the force is ready.
		bay_button = kit.button("Mech Bay", func(): Flow.proceed_from_briefing(), true)
		bay_button.custom_minimum_size.x = kit.em(10)
		bay_button.disabled = not brief.available
		h.add_child(bay_button)
		launch_button = kit.button("Launch", func():
			Flow.save_progress()
			Flow.launch())
		var problem := Flow.campaign.launch_problem(brief.mission)
		launch_button.disabled = problem != "" or not brief.available
		launch_note.text = problem
	else:
		launch_button = kit.button("Launch mission", func(): Flow.proceed_from_briefing(), true)
		launch_button.disabled = not brief.available
		if not brief.available:
			launch_note.text = "Not yet available"
	launch_button.custom_minimum_size.x = kit.em(10)
	h.add_child(launch_button)


# --- objectives ---------------------------------------------------------------------------

## Select objective n (1-based): highlight its row and marker, show its model in the target
## view. by_user stops the 3-second cycling, as a click does in the original.
func select_objective(n: int, by_user := false) -> void:
	if by_user:
		user_picked = true
	if n < 1 or n > numbered.size():
		return
	var old := selected
	selected = n
	_style_row(old)
	_style_row(n)
	if map:
		map.set_selected(n)
	var o: Dictionary = numbered[n - 1][1]
	var kind := _model_kind(o)
	var shown := false
	if kind != "":
		var paint: Array = o.get("model_paint", [])
		if paint.size() == 3 and paint.all(func(c): return int(c) == -1):
			paint = []  # no colours given: the model's own
		shown = target.show_model(kind, String(o["model"]).to_lower(), paint)
	if not shown:
		target.studio.clear()
	target_label.text = ("Target %d · %s" % [n, _model_name(o)]) if shown else "Objective %d · no target imagery" % n


## "mech", "vehicle", "object" for an objective's ObjectiveModel (ModelType 13 'Mech, 5
## vehicle, 14 building), "" when there is none.
static func _model_kind(o: Dictionary) -> String:
	if String(o.get("model", "")) == "":
		return ""
	match int(o.get("model_type", 0)):
		13: return "mech"
		5: return "vehicle"
	return "object"


static func _model_name(o: Dictionary) -> String:
	var key := String(o["model"]).to_lower()
	if GameData.chassis.has(key):
		return String(GameData.chassis[key]["name"])
	var n := RegEx.create_from_string("([a-z])([A-Z])").sub(String(o["model"]).trim_prefix("D_").trim_prefix("S_").trim_prefix("L_"), "$1 $2", true)
	return RegEx.create_from_string("([A-Z]+)([A-Z][a-z])").sub(n, "$1 $2", true)


func _process(delta: float) -> void:
	if user_picked or numbered.size() < 2:
		return
	_cycle_t += delta
	if _cycle_t >= CYCLE_S:
		_cycle_t = 0.0
		select_objective(selected % numbered.size() + 1)


func _start_video(name: String) -> void:
	if name == "" or not FileAccess.file_exists("res://data/videos.json"):
		return
	var videos: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/videos.json"))
	var path := String(videos.get(name, ""))
	if path == "" or not ResourceLoader.exists(path):
		return
	video.stream = load(path)
	video.visible = true
	target.visible = false
	video.play()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ENTER, KEY_KP_ENTER]:
		var main := bay_button if bay_button else launch_button
		if main and not main.disabled:
			Flow.proceed_from_briefing()


func _play_tune(tune: int) -> void:
	if tune < 0 or not FileAccess.file_exists("res://data/audio.json"):
		return
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))
	var path := String(manifest.get("music", {}).get(str(tune), ""))
	if path == "" or not ResourceLoader.exists(path):
		return
	music = AudioStreamPlayer.new()
	music.stream = load(path)
	music.volume_db = -8.0
	add_child(music)
	music.play()


## A legend swatch: a ring (objective) or a diamond (drop zone).
class Legend:
	extends Control
	var colour := Color.WHITE
	var shape := "o"

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var c := size / 2.0
		var r := minf(size.x, size.y) * 0.42
		if shape == "d":
			var pts := PackedVector2Array([c + Vector2(0, -r), c + Vector2(r, 0), c + Vector2(0, r), c + Vector2(-r, 0), c + Vector2(0, -r)])
			draw_colored_polygon(pts.slice(0, 4), Color(colour, 0.35))
			draw_polyline(pts, colour, 2.0, true)
		else:
			draw_circle(c, r, Color(0.02, 0.06, 0.09, 0.8))
			draw_arc(c, r, 0.0, TAU, 24, colour, 2.0, true)
