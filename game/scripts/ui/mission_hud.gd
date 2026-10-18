class_name MissionHud
extends CanvasLayer
## The mission HUD: force bar of unit cards (bottom left), tactical minimap
## (bottom right), weapons panel for the selected unit, objectives (top right),
## message log, top bar with time and help, and the end-of-mission banner.

const MAX_MESSAGES := 6
const MESSAGE_LIFE := 8.0

var view: Node  # mission_view
var cards: Dictionary = {}  # unit id -> UnitCard
var minimap: Minimap
var force_bar: HBoxContainer
var weapons_panel: Control
var objectives_label: Label
var top_label: Label
var log_label: Label
var banner: Label
var box: ColorRect
var _messages: Array = []  # [text, time]


func setup(mission_view: Node) -> void:
	view = mission_view
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	top_label = _label(15)
	top_label.position = Vector2(14, 10)
	root.add_child(top_label)

	objectives_label = _label(16)
	objectives_label.anchor_left = 1.0
	objectives_label.anchor_right = 1.0
	objectives_label.offset_left = -540
	objectives_label.offset_right = -14
	objectives_label.offset_top = 10
	objectives_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	root.add_child(objectives_label)

	force_bar = HBoxContainer.new()
	force_bar.anchor_top = 1.0
	force_bar.anchor_bottom = 1.0
	force_bar.offset_left = 12
	force_bar.offset_top = -152
	force_bar.add_theme_constant_override("separation", 6)
	root.add_child(force_bar)
	for u in view.world.units:
		if u.team == view.sm.player_team and u.is_mover():
			var c := UnitCard.new(u)
			c.picked.connect(_on_card_picked)
			force_bar.add_child(c)
			cards[u.id] = c

	weapons_panel = WeaponsPanel.new()
	weapons_panel.hud = self
	weapons_panel.anchor_top = 1.0
	weapons_panel.anchor_bottom = 1.0
	weapons_panel.offset_left = 12
	weapons_panel.offset_top = -152 - 8 - 150
	weapons_panel.offset_right = 12 + 300
	weapons_panel.offset_bottom = -152 - 8
	root.add_child(weapons_panel)

	log_label = _label(15)
	log_label.anchor_top = 1.0
	log_label.anchor_bottom = 1.0
	log_label.offset_left = 330
	log_label.offset_top = -152 - 8 - 150
	log_label.offset_right = 900
	log_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	log_label.offset_bottom = -152 - 8
	root.add_child(log_label)

	minimap = Minimap.new()
	minimap.anchor_left = 1.0
	minimap.anchor_right = 1.0
	minimap.anchor_top = 1.0
	minimap.anchor_bottom = 1.0
	minimap.offset_left = -272
	minimap.offset_right = -12
	minimap.offset_top = -272
	minimap.offset_bottom = -12
	root.add_child(minimap)
	minimap.setup(view.world, view.sm.objectives, "res://assets/maps/%s/burnin.jpg" % view.mission, view.sm.player_team)
	minimap.pan_to.connect(func(p: Vector2): view.camera.focus = Vector3(p.x, 0, -p.y))
	minimap.move_to.connect(_on_minimap_move)

	banner = _label(64)
	banner.set_anchors_preset(Control.PRESET_CENTER)
	banner.add_theme_constant_override("outline_size", 10)
	banner.visible = false
	root.add_child(banner)

	box = ColorRect.new()
	box.color = Color(0.3, 1.0, 0.4, 0.15)
	box.visible = false
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(box)


func _label(px: int) -> Label:
	var l := Label.new()
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_size_override("font_size", px)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", 4)
	return l


func _on_card_picked(u: SimUnit, add: bool) -> void:
	var s: Array = view.input.selection.duplicate() if add else []
	if not s.has(u):
		s.append(u)
	view.input._set_selection(s)


func _on_minimap_move(p: Vector2) -> void:
	for m in view.input.selection:
		view.world.order_move(m, p)


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
			if u.team == view.sm.player_team and u.is_mover():
				message("%s is down!" % u.name)
			elif u.is_mover():
				message("%s destroyed" % u.name)
			elif u is SimStructure:
				message("%s destroyed" % u.name)
		"fell":
			var u: SimUnit = w.units[e["unit"]]
			if u.team == view.sm.player_team:
				message("%s has fallen" % u.name)


func _objective_title(obj: Dictionary) -> String:
	var t: String = GameData.string(obj["title_string"]) if obj["title_string"] > 0 else ""
	return t if not t.is_empty() else String(obj["title"])


func _process(_delta: float) -> void:
	var w: SimWorld = view.world
	top_label.text = "%s   %02d:%02d      LMB select · RMB move/attack · H hold · F alpha strike · WASD/QE/wheel camera" % [
		view.mission, int(w.time) / 60, int(w.time) % 60]
	var lines: Array[String] = ["OBJECTIVES"]
	for obj in view.sm.objectives.visible_objectives():
		lines.append(("✔ " if obj["complete"] else "• ") + _objective_title(obj))
	objectives_label.text = "\n".join(lines)
	var keep := []
	for m in _messages:
		if w.time - m[1] < MESSAGE_LIFE:
			keep.append(m)
	_messages = keep
	log_label.text = "\n".join(_messages.map(func(m): return m[0]))
	for id in cards:
		cards[id].selected = view.input.selection.has(w.units[id])
	minimap.view_polygon = _camera_footprint()
	var res: int = view.sm.objectives.result
	if res != SimObjectives.Result.PLAYING and not banner.visible:
		banner.visible = true
		banner.text = "MISSION SUCCESSFUL" if res == SimObjectives.Result.WON else "MISSION FAILED"
		banner.add_theme_color_override("font_color", Color(0.5, 1.0, 0.5) if res == SimObjectives.Result.WON else Color(1.0, 0.4, 0.3))
		banner.position = get_viewport().get_visible_rect().size / 2.0 - banner.get_minimum_size() / 2.0


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


class WeaponsPanel:
	extends Control
	## Weapons of the first selected unit: name, range, recycle progress, ammo.
	var hud

	func _process(_delta: float) -> void:
		queue_redraw()

	func _draw() -> void:
		var sel: Array = hud.view.input.selection
		if sel.is_empty():
			return
		var u: SimUnit = sel[0]
		var font := get_theme_default_font()
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.05, 0.07, 0.08, 0.8))
		draw_string(font, Vector2(8, 16), "%s — weapons" % u.name, HORIZONTAL_ALIGNMENT_LEFT, size.x - 16, 13, Color(0.9, 0.95, 0.9))
		var now: float = hud.view.world.time
		var y := 32.0
		for w in u.weapon_indices():
			if y > size.y - 6:
				break
			var item: Dictionary = u.items[w]
			var wd := u.weapon(w)
			var dead: bool = item["disabled"]
			var col := Color(0.45, 0.45, 0.45) if dead else Color(0.85, 0.9, 0.85)
			draw_string(font, Vector2(8, y + 9), item["component"]["name"], HORIZONTAL_ALIGNMENT_LEFT, 150, 11, col)
			draw_string(font, Vector2(160, y + 9), String(wd.get("range", "")).left(3).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, 30, 10, col)
			var shots := u.weapon_shots(w)
			draw_string(font, Vector2(190, y + 9), "∞" if shots < 0 else str(shots), HORIZONTAL_ALIGNMENT_LEFT, 40, 10, col)
			var recycle := float(wd.get("recycle", 1.0))
			var frac := 1.0 - clampf((float(item["ready_time"]) - now) / maxf(recycle, 0.01), 0.0, 1.0)
			var r := Rect2(230, y + 2, size.x - 238, 7)
			draw_rect(r, Color(0.15, 0.15, 0.15))
			draw_rect(Rect2(r.position, Vector2(r.size.x * frac, r.size.y)), Color(0.3, 0.8, 0.9) if frac >= 1.0 else Color(0.25, 0.5, 0.6))
			y += 14.0
