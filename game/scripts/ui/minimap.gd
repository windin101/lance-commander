class_name Minimap
extends Control
## Tactical map: colour map with water tinted by depth, units as dots (player
## green, enemy red, structures grey), objective markers, and the camera's view.
## Left-click/drag pans the camera; right-click moves the selection there.

signal pan_to(world_pos: Vector2)
signal move_to(world_pos: Vector2)

var map: SimMap
var world: SimWorld
var objectives: SimObjectives
var player_team := 0
var view_polygon := PackedVector2Array()  # world positions of the camera view corners
var _tex: ImageTexture
var _dragging := false


func setup(sim_world: SimWorld, sim_objectives: SimObjectives, colour_map_path: String, team: int) -> void:
	world = sim_world
	map = sim_world.map
	objectives = sim_objectives
	player_team = team
	custom_minimum_size = Vector2(260, 260)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_tex = ImageTexture.create_from_image(build_image(map, colour_map_path, 256))


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


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0, 0, 0, 0.8))
	if _tex:
		draw_texture_rect(_tex, Rect2(Vector2.ZERO, size), false)
	for u in world.units:
		if u is SimStructure:
			if not u.is_destroyed() and u.damage_level < 100000.0:
				draw_rect(Rect2(world_to_map(u.position) - Vector2(1.5, 1.5), Vector2(3, 3)), Color(0.75, 0.75, 0.75, 0.8))
	for u in world.units:
		if not u.is_mover():
			continue
		var p := world_to_map(u.position)
		if u.is_disabled():
			draw_circle(p, 1.5, Color(0.2, 0.2, 0.2))
		elif u.team == player_team:
			draw_circle(p, 3.0, Color(0.3, 1.0, 0.4))
		else:
			draw_circle(p, 2.5 if u is SimMech else 1.8, Color(1.0, 0.25, 0.2))
	if objectives:
		var blink := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 200.0)
		for obj in objectives.visible_objectives():
			if obj["complete"] or not obj["show_marker"]:
				continue
			var p := world_to_map(obj["marker"])
			var d := 6.0
			draw_colored_polygon(PackedVector2Array([p + Vector2(0, -d), p + Vector2(d, 0), p + Vector2(0, d), p + Vector2(-d, 0)]),
				Color(1.0, 0.9, 0.2, 0.5 + 0.5 * blink))
	if view_polygon.size() == 4:
		var pts := PackedVector2Array()
		for wp in view_polygon:
			pts.append(world_to_map(wp))
		pts.append(pts[0])
		draw_polyline(pts, Color(1, 1, 1, 0.8), 1.5)
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.35, 0.4, 0.42), false, 2.0)
