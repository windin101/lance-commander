class_name CommandInput
extends Node
## RTS commands: left-click / drag-box to select player units, right-click on an
## enemy unit or a destructible building to attack it, or on the ground to move
## there. H = hold.

signal selection_changed(mechs: Array)

const PICK_PX := 40.0

var abl: SimAbl = null  # the mission's ABL bridge: player orders go to the lance's pbrain
var support: SimSupport = null
var support_kind := ""  # a support power waiting for its target (HUD button pressed)
var world: SimWorld
var views: Dictionary = {}  # mech id -> MechView
var camera: Camera3D
var selection: Array[SimUnit] = []
var player_team := 0
var _drag_start := Vector2.ZERO
var _dragging := false
var box: ColorRect


func _unhandled_input(event: InputEvent) -> void:
	if world and world.movie_mode:  # mission cinematic: player input off, as in the original (missiongui.cpp:430)
		return
	if support_kind != "" and _support_input(event):
		get_viewport().set_input_as_handled()
		return
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
			_order(m, "stop")
	elif event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F:
		toggle_alpha_strike()


## Toggle "alpha strike" (ignore heat discipline) for the selection; all on unless all already on.
func toggle_alpha_strike() -> void:
	var all_on := not selection.is_empty() and selection.all(func(m): return m.ignore_heat_discipline)
	for m in selection:
		m.ignore_heat_discipline = not all_on


## The mech nearest a screen point (within PICK_PX), optionally filtered by team.
func mech_at(screen: Vector2, team: int = -1, include_disabled := false) -> SimUnit:
	var best: SimUnit = null
	var best_d := PICK_PX
	for m in world.units:
		if (m.is_disabled() and not include_disabled) or (team >= 0 and m.team != team) or not views.has(m.id):
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
		if not (u is SimStructure) or u.is_destroyed() or (u.damage_level >= 100000.0 and not u.capturable):
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
		if m.team != player_team or m.is_disabled() or not m.on_gui or not views.has(m.id) or not m.is_mover():
			continue
		var v: MechView = views[m.id]
		if not camera.is_position_behind(v.aim_point()) and rect.has_point(camera.unproject_position(v.aim_point())):
			if not s.has(m):
				s.append(m)
	_set_selection(s)


## Targeting a support power: left-click places it (a ground point, or a disabled mech
## for the salvage craft); right-click or Esc cancels. Returns true if it used the event.
func _support_input(event: InputEvent) -> bool:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		support_kind = ""
		return true
	if not (event is InputEventMouseButton and event.pressed):
		return false
	if event.button_index == MOUSE_BUTTON_RIGHT:
		support_kind = ""
		return true
	if event.button_index != MOUSE_BUTTON_LEFT:
		return false
	var target = mech_at(event.position, -1, true) if support_kind == "salvage_craft" else ground_at(event.position)
	if support and target != null and support.call_power(support_kind, target):
		support_kind = ""
	else:
		world.events.append({"type": "support_refused", "kind": support_kind})
	return true


func _command(screen: Vector2) -> void:
	if selection.is_empty():
		return
	# A selected repair truck services the damaged friendly mech clicked (support-powers.md 3.4).
	var trucks := selection.filter(func(u): return u.refit_pool > 0.0)
	if support and not trucks.is_empty():
		var friend := mech_at(screen, player_team)
		if friend is SimMech:
			for t in trucks:
				support.order_repair(t, friend)
			return
	var enemy := mech_at(screen)
	if enemy == null or enemy.team == player_team:
		enemy = structure_at(screen)
	# A capturable target always means capture (capture-and-objectives.md A2); only an
	# all-mech selection may capture, otherwise the click is refused.
	if enemy and abl and abl.can_capture(enemy, player_team):
		if selection.all(func(m): return m is SimMech):
			for m in selection:
				_order(m, "capture", enemy)
		else:
			world.events.append({"type": "capture_refused", "unit": selection[0].id, "target": enemy.id})
		return
	if enemy and enemy.team != player_team:
		for m in selection:
			_order(m, "attack", enemy)
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
		_order(selection[i], "move", g + offset)


## Player orders go through the unit's pbrain (SimAbl) when it has one, as in the
## original; otherwise straight to the world.
func _order(m: SimUnit, kind: String, arg: Variant = null) -> void:
	if abl and m.brain is SimAbl.Pilot:
		abl.player_order(m, kind, arg)
		return
	match kind:
		"attack":
			world.order_attack(m, arg)
		"move":
			world.order_move(m, arg)
		_:
			world.order_hold(m)


func _set_selection(s: Array) -> void:
	for m in selection:
		if views.has(m.id):
			views[m.id].selected = false
	selection.assign(s)
	for m in selection:
		views[m.id].selected = true
	selection_changed.emit(selection)
