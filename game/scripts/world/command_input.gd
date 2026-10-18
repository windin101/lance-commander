class_name CommandInput
extends Node
## RTS commands: left-click / drag-box to select player units, right-click on an
## enemy unit or a destructible building to attack it, or on the ground to move
## there. H = hold.

signal selection_changed(mechs: Array)

const PICK_PX := 40.0

var world: SimWorld
var views: Dictionary = {}  # mech id -> MechView
var camera: Camera3D
var selection: Array[SimUnit] = []
var player_team := 0
var _drag_start := Vector2.ZERO
var _dragging := false
var box: ColorRect


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_drag_start = event.position
				_dragging = true
			elif _dragging:
				_dragging = false
				if box:
					box.visible = false
				if _drag_start.distance_to(event.position) > 8.0:
					_select_box(Rect2(_drag_start, event.position - _drag_start).abs(), event.shift_pressed)
				else:
					_select_click(event.position, event.shift_pressed)
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			_command(event.position)
	elif event is InputEventMouseMotion and _dragging and box:
		var r := Rect2(_drag_start, event.position - _drag_start).abs()
		box.position = r.position
		box.size = r.size
		box.visible = r.size.length() > 8.0
	elif event is InputEventKey and event.pressed and event.keycode == KEY_H:
		for m in selection:
			world.order_hold(m)
	elif event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F:
		toggle_alpha_strike()


## Toggle "alpha strike" (ignore heat discipline) for the selection; all on unless all already on.
func toggle_alpha_strike() -> void:
	var all_on := not selection.is_empty() and selection.all(func(m): return m.ignore_heat_discipline)
	for m in selection:
		m.ignore_heat_discipline = not all_on


## The mech nearest a screen point (within PICK_PX), optionally filtered by team.
func mech_at(screen: Vector2, team: int = -1) -> SimUnit:
	var best: SimUnit = null
	var best_d := PICK_PX
	for m in world.units:
		if m.is_disabled() or (team >= 0 and m.team != team) or not views.has(m.id):
			continue
		var v: MechView = views[m.id]
		if camera.is_position_behind(v.aim_point()):
			continue
		var d := camera.unproject_position(v.aim_point()).distance_to(screen)
		if d < best_d:
			best_d = d
			best = m
	return best


## A destructible building under a screen point (its footprint centre, raised a little).
func structure_at(screen: Vector2) -> SimUnit:
	var best: SimUnit = null
	var best_d := PICK_PX * 1.5
	for u in world.units:
		if not (u is SimStructure) or u.is_destroyed() or u.damage_level >= 100000.0:
			continue
		var p := TerrainView.to_3d(u.position, world.map.height_at(u.position) + 4.0)
		if camera.is_position_behind(p):
			continue
		var d := camera.unproject_position(p).distance_to(screen)
		if d < best_d:
			best_d = d
			best = u
	return best


## Ground point under a screen position, by marching the camera ray over the heightmap.
func ground_at(screen: Vector2) -> Variant:
	var origin := camera.project_ray_origin(screen)
	var dir := camera.project_ray_normal(screen)
	var t := 0.0
	var prev := origin
	while t < 5000.0:
		var p := origin + dir * t
		var h := world.map.height_at(Vector2(p.x, -p.z))
		if p.y <= h:
			for i in 12:  # bisect between prev and p
				var mid := (prev + p) / 2.0
				if mid.y <= world.map.height_at(Vector2(mid.x, -mid.z)):
					p = mid
				else:
					prev = mid
			return Vector2(p.x, -p.z)
		prev = p
		t += 4.0
	return null


func _select_click(screen: Vector2, add: bool) -> void:
	var m := mech_at(screen, player_team)
	if not add:
		_set_selection([])
	if m:
		var s := selection.duplicate()
		if not s.has(m):
			s.append(m)
		_set_selection(s)


func _select_box(rect: Rect2, add: bool) -> void:
	var s: Array[SimUnit] = selection.duplicate() if add else []
	for m in world.units:
		if m.team != player_team or m.is_disabled() or not views.has(m.id) or not m.is_mover():
			continue
		var v: MechView = views[m.id]
		if not camera.is_position_behind(v.aim_point()) and rect.has_point(camera.unproject_position(v.aim_point())):
			if not s.has(m):
				s.append(m)
	_set_selection(s)


func _command(screen: Vector2) -> void:
	if selection.is_empty():
		return
	var enemy := mech_at(screen)
	if enemy == null or enemy.team == player_team:
		enemy = structure_at(screen)
	if enemy and enemy.team != player_team:
		for m in selection:
			world.order_attack(m, enemy)
		return
	var g = ground_at(screen)
	if g == null:
		return
	# Spread a group around the click so they don't queue on one cell.
	var n := selection.size()
	for i in n:
		var offset := Vector2.ZERO
		if n > 1:
			var a := TAU * i / n
			offset = Vector2(cos(a), sin(a)) * 14.0
		world.order_move(selection[i], g + offset)


func _set_selection(s: Array) -> void:
	for m in selection:
		if views.has(m.id):
			views[m.id].selected = false
	selection.assign(s)
	for m in selection:
		views[m.id].selected = true
	selection_changed.emit(selection)
