class_name Minimap
extends Control
## Tactical map: colour map with water tinted by depth, units as dots (player
## green, allies blue, enemy contacts red, structures grey) with the original's sensor
## rings, objective markers, and the camera's view.
## Left-click/drag pans the camera; right-click moves the selection there.
## Drawn in the HUD's tac-map style (approved mock-up): faint cyan grid, the camera
## footprint as a light wedge, amber objective markers, N in the corner. The frame and
## caption belong to MissionHud's tac-map panel.

signal pan_to(world_pos: Vector2)
signal move_to(world_pos: Vector2)

var map: SimMap
var world: SimWorld
var objectives: SimObjectives
var player_team := 0
var view_polygon := PackedVector2Array()  # world positions of the camera view corners
var ui_unit := 11.4  # HUD base unit, for marker and label sizes
var _tex: ImageTexture
var _dragging := false


## texture: a map image already built (the HUD keeps it across rebuilds), else built here.
func setup(sim_world: SimWorld, sim_objectives: SimObjectives, colour_map_path: String, team: int, texture: ImageTexture = null) -> void:
	world = sim_world
	map = sim_world.map
	objectives = sim_objectives
	player_team = team
	if custom_minimum_size == Vector2.ZERO:
		custom_minimum_size = Vector2(260, 260)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_tex = texture if texture else ImageTexture.create_from_image(build_image(map, colour_map_path, 256))


func texture() -> ImageTexture:
	return _tex


## Minimap image: the colour map, darkened and blued below the waterline.
static func build_image(sim_map: SimMap, colour_map_path: String, px: int) -> Image:
	var img: Image
	var tex = load(colour_map_path)
	if tex:
		img = (tex as Texture2D).get_image()
		img.decompress()
		img.convert(Image.FORMAT_RGB8)
		img.resize(px, px, Image.INTERPOLATE_BILINEAR)
	else:
		img = Image.create(px, px, false, Image.FORMAT_RGB8)
		img.fill(Color(0.45, 0.4, 0.3))
	var water := Color(0.10, 0.22, 0.32)
	for y in px:
		for x in px:
			var p := Vector2(-sim_map.half_m + (x + 0.5) * 2.0 * sim_map.half_m / px, sim_map.half_m - (y + 0.5) * 2.0 * sim_map.half_m / px)
			var depth := sim_map.water_level_m - sim_map.height_at(p)
			if depth > 0.0:
				img.set_pixel(x, y, img.get_pixel(x, y).lerp(water, clampf(0.55 + depth / 20.0, 0.55, 0.9)))
	return img


func world_to_map(p: Vector2) -> Vector2:
	return Vector2((p.x + map.half_m) / (2.0 * map.half_m), (map.half_m - p.y) / (2.0 * map.half_m)) * size


func map_to_world(m: Vector2) -> Vector2:
	var f := m / size
	return Vector2(-map.half_m + f.x * 2.0 * map.half_m, map.half_m - f.y * 2.0 * map.half_m)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			_dragging = event.pressed
			if event.pressed:
				pan_to.emit(map_to_world(event.position))
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			move_to.emit(map_to_world(event.position))
		accept_event()
	elif event is InputEventMouseMotion and _dragging:
		pan_to.emit(map_to_world(event.position))
		accept_event()


func _process(_delta: float) -> void:
	queue_redraw()


## Allied (player team, another commander) blip and ring colour; the original used blue.
const ALLY := Color(0.36, 0.6, 1.0)


## An enemy mover the player's team has as a contact, not shut down and without ECM: the
## only enemies the original's tac map draws (GameTacMap::render, gameTacMap.cpp:385-395).
func _enemy_shown(u: SimUnit) -> bool:
	return u.exists and u.status != SimUnit.Status.SHUTDOWN and not u.has_ecm() and world.is_contact(player_team, u)


## The sensor ring of one unit (GameTacMap::drawSensor, gameTacMap.cpp:465-509): a circle of
## the sensor range plus six cells' "fudge", scaled to the map.
func sensor_ring_px(range_m: float) -> float:
	if range_m <= 1.0:
		return 0.0
	return (range_m + map.cell_m * 6.0) / (2.0 * map.half_m) * size.x


## Every sensor ring the original draws: the home commander's movers (green, on the GUI, not
## shut down), allies (blue), enemy contacts (red), and sensor towers by owner.
func rings() -> Array:
	var out := []  # [map point, radius px, colour]
	for u in world.units:
		var col := Color(0, 0, 0, 0)
		var r := 0.0
		if u.is_mover():
			if not u.exists or u.is_disabled() or u.status == SimUnit.Status.SHUTDOWN:
				continue
			if u.team == player_team:
				if u.commander == 0 and not u.on_gui:
					continue
				col = UiStyle.HUD_OK if u.commander == 0 else ALLY
			elif _enemy_shown(u):
				col = UiStyle.HUD_CRIT
			else:
				continue
			r = sensor_ring_px(u.sensor_range())
		elif u is SimStructure and (u as SimStructure).sensor_works():
			col = UiStyle.HUD_OK if u.team == player_team else UiStyle.HUD_CRIT
			r = sensor_ring_px((u as SimStructure).tower_sensor_m)
		if r > 0.0:
			out.append([world_to_map(u.position), r, col])
	return out


func _draw_sensor_rings() -> void:
	for ring in rings():
		draw_arc(ring[0], ring[1], 0.0, TAU, maxi(24, int(ring[1])), Color(ring[2], 0.55), 1.0, true)


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.027, 0.063, 0.09))
	if _tex:
		draw_texture_rect(_tex, Rect2(Vector2.ZERO, size), false)
	var grid := Color(UiStyle.HUD_EDGE, 0.18)
	for k in range(1, 8):
		var t := size * (k / 8.0)
		draw_line(Vector2(t.x, 0), Vector2(t.x, size.y), grid, 1.0)
		draw_line(Vector2(0, t.y), Vector2(size.x, t.y), grid, 1.0)
	var dot := maxf(2.0, size.x / 62.0)
	_draw_sensor_rings()
	for u in world.units:
		if u is SimTurret:
			# map turrets (I94): a small triangle in the owner's colour; dim once its control is lost
			if not u.is_destroyed():
				var tp := world_to_map(u.position)
				var col: Color = UiStyle.HUD_OK if u.team == player_team else (UiStyle.HUD_CRIT if u.team >= 0 else UiStyle.HUD_INK)
				if not u.active:
					col = Color(col, 0.35)
				draw_colored_polygon(PackedVector2Array([tp + Vector2(0, -dot * 0.8), tp + Vector2(dot * 0.7, dot * 0.5),
					tp + Vector2(-dot * 0.7, dot * 0.5)]), col)
		elif u is SimStructure:
			if not u.is_destroyed() and u.damage_level < 100000.0:
				draw_rect(Rect2(world_to_map(u.position) - Vector2(dot, dot) * 0.5, Vector2(dot, dot)), Color(UiStyle.HUD_INK, 0.6))
	if view_polygon.size() == 4:
		var pts := PackedVector2Array()
		for wp in view_polygon:
			pts.append(world_to_map(wp).clamp(Vector2.ZERO, size))
		if Geometry2D.triangulate_polygon(pts).size() > 0:
			draw_colored_polygon(pts, Color(UiStyle.HUD_INK, 0.10))
		pts.append(pts[0])
		draw_polyline(pts, UiStyle.HUD_INK, 1.2, true)
	for u in world.units:
		if not u.is_mover():
			continue
		var p := world_to_map(u.position)
		if u.is_disabled():
			draw_circle(p, dot * 0.6, Color(0.2, 0.2, 0.2))
		elif u.team == player_team and not u.on_gui:
			continue  # off the GUI (gameTacMap.cpp:370)
		elif u.team == player_team:
			draw_circle(p, dot, UiStyle.HUD_OK if u.commander == 0 else ALLY)
		elif _enemy_shown(u):
			draw_circle(p, dot * (1.0 if u is SimMech else 0.75), UiStyle.HUD_CRIT)
	if objectives:
		var blink := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 200.0)
		for obj in objectives.visible_objectives():
			if obj["complete"] or not obj["show_marker"]:
				continue
			var p := world_to_map(obj["marker"])
			var d := dot * 1.6
			draw_rect(Rect2(p - Vector2(d, d), Vector2(d, d) * 2.0), Color(UiStyle.HUD_WARN, 0.6 + 0.4 * blink), false, maxf(1.0, dot * 0.5))
	var f := UiStyle.font("mono")
	var fs := maxi(6, roundi(ui_unit * 1.0))
	draw_string(f, Vector2(size.x - ui_unit * 0.4 - f.get_string_size("N", HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x, ui_unit * 0.3 + f.get_ascent(fs)),
		"N", HORIZONTAL_ALIGNMENT_LEFT, -1, fs, UiStyle.HUD_EDGE)
	draw_rect(Rect2(Vector2.ZERO, size), UiStyle.HUD_EDGE_SOFT, false, 1.0)
