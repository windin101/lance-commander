class_name CommandInput
extends Node
## RTS commands: left-click / drag-box to select player units, right-click on an
## enemy unit or a destructible building to attack it, or on the ground to move
## there. A = alpha strike (the original's A is energy weapons only; F is its force fire,
## missiongui.cpp:202-208).
## Order modes as the original's command palette (ControlGui curOrder, controlGui.cpp:120-123,
## 1340-1395): Run, Guard and Jump arm the next right-click; Run combines with Guard, Jump is
## alone. A button toggles its mode and it stays armed until an order uses it (doMove / doJump /
## doGuard call setDefaultSpeed; an attack keeps Run and clears fire-from-position,
## missiongui.cpp:1893). A hotkey arms it only while held (the key table's press / release
## pairs, missiongui.cpp:198-226, run by update(), :1745-1788): Space = run, J = jump,
## G = guard, C = fire from current position. Backspace = stop (removeCommand -> doStop) and
## H toggles hold position (toggleHoldPosition, controlGui.cpp:2895); both act at once.
## Without Run a player order walks (WALK = 0 is the default, TRAVEL_MODE_SLOW).
## Groups as in the original (selectForceGroup / makeForceGroup, missiongui.cpp:3240-3298):
## 0-9 selects that group, Shift+0-9 adds it (or drops it when it is all selected already),
## Ctrl+0-9 assigns the selection to it. E selects every own unit on screen, Shift+E adds them
## (selectVisible / addVisibleToSelection, missiongui.cpp:2069-2107). Double-clicking a friendly
## unit selects its group(s) and makes the camera follow it (setTarget, missiongui.cpp:3307-3311).

signal selection_changed(mechs: Array)
signal groups_changed(groups: Dictionary)

const PICK_PX := 40.0
const DRAG_PX := 10.0  # a left press that moves further than this is a box select
const RUN := 1  # ControlGui::RUN / GUARD / JUMP (controlGui.cpp:120-123)
const GUARD := 2
const JUMP := 4
const MODE_BITS := {"run": RUN, "guard": GUARD, "jump": JUMP}
## Held keys -> the mode they arm while down (missiongui.cpp:203-226).
## S / M / L arm the short, medium and long attack range while held (attackShort / attackMedium /
## attackLong, missiongui.cpp:196-198, 1896-1931; released: defaultAttack, FIRERANGE_OPTIMAL);
## F is force fire (forceShot, missiongui.cpp:206, 3208-3240).
const MODE_KEYS := {KEY_SPACE: "run", KEY_J: "jump", KEY_G: "guard", KEY_C: "fire_from_position",
	KEY_S: "short", KEY_M: "medium", KEY_L: "long", KEY_F: "force_fire",
	KEY_KP_2: "aim_leg", KEY_KP_5: "aim_arm", KEY_KP_8: "aim_head", KEY_END: "eject"}
## Aimed shots: Numpad 2 / 5 / 8 held + right-click an enemy ground 'Mech (aimLeg / aimArm / aimHead,
## missiongui.cpp:217-219, 2109-2265). End held + click your own 'Mech ejects its pilot (eject,
## missiongui.cpp:226, 2303-2318). PgDn / PgUp power the selection down and up (2273-2289).
const AIMS := ["aim_leg", "aim_arm", "aim_head"]
const RANGES := ["short", "medium", "long"]
## Waypoints: orders given with the waypoint key (left Ctrl, missiongui.cpp:842-843) held are
## queued and run in order when it is released (missiongui.cpp:1703-1722, 2505-2509).
const WAYPOINT_KEY := KEY_CTRL

var abl: SimAbl = null  # the mission's ABL bridge: player orders go to the lance's pbrain
var support: SimSupport = null
var support_kind := ""  # a support power waiting for its target (HUD button pressed)
var world: SimWorld
var views: Dictionary = {}  # mech id -> MechView
var camera: Camera3D
var selection: Array[SimUnit] = []
var groups: Dictionary = {}  # 0-9 -> Array of SimUnit; per mission (this node lives with the mission)
var player_team := 0
var _drag_start := Vector2.ZERO
var _dragging := false
var _double := false  # the release after a double-click must not re-run the single click
var box: ColorRect
var mode_bits := 0  # the toggled palette modes (curOrder)
var fire_from_position := false  # ControlGui fireFromCurrentPos
var range_mode := ""  # ControlGui setRange: "" (FIRERANGE_OPTIMAL) or short / medium / long (the range buttons)
var force_fire := false  # the force-fire button: the next right-click is a forced shot
var suppress := false  # the GUARDTOWER button (controlGui.cpp:2200-2228): artillery pieces shell a point
var lay_mines := false  # the LAYMINES button (controlGui.cpp:1110-1117): a minelayer's moves lay mines
var _queued: Array[SimUnit] = []  # units given waypoints since the waypoint key went down
var _held := {}  # mode keys held down -> their mode
## The armed mode as one name ("" = none) for the HUD: jump, guard, run, then fire from position.
## Setting it arms exactly that mode ("" disarms all).
var order_mode: String:
	get:
		for k in ["jump", "guard", "run", "fire_from_position"]:
			if mode_on(k):
				return k
		return ""
	set(v):
		mode_bits = 0
		fire_from_position = false
		if v != "":
			toggle_mode(v)


func _unhandled_input(event: InputEvent) -> void:
	if world and world.movie_mode:  # mission cinematic: player input off, as in the original (missiongui.cpp:430)
		if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
			world.force_movie_end = true  # Esc asks the script to end it (missiongui.cpp:435-436)
			get_viewport().set_input_as_handled()
		return
	if support_kind != "" and _support_input(event):
		get_viewport().set_input_as_handled()
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed and event.double_click:
				_dragging = false
				_double = true
				_double_click(event.position)
			elif event.pressed:
				_drag_start = event.position
				_dragging = true
			elif _double:
				_double = false
			elif _dragging:
				_dragging = false
				if box:
					box.visible = false
				if _drag_start.distance_to(event.position) > DRAG_PX:
					_select_box(Rect2(_drag_start, event.position - _drag_start).abs(), event.shift_pressed)
				else:
					_select_click(event.position, event.shift_pressed)
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			_command(event.position)
	elif event is InputEventMouseMotion and _dragging and box:
		var r := Rect2(_drag_start, event.position - _drag_start).abs()
		box.position = r.position
		box.size = r.size
		box.visible = _drag_start.distance_to(event.position) > DRAG_PX
	elif event is InputEventKey and event.pressed and not event.alt_pressed:
		_key(event)


func _key(event: InputEventKey) -> void:
	if event.echo:
		if MODE_KEYS.has(event.keycode):
			get_viewport().set_input_as_handled()
		return
	if MODE_KEYS.has(event.keycode) and not event.ctrl_pressed:
		hold_mode_key(event.keycode, true)
	elif event.keycode == KEY_BACKSPACE:
		stop()
	elif event.keycode == KEY_PAGEDOWN or event.keycode == KEY_PAGEUP:
		for m in selection:
			_order(m, "power_up" if event.keycode == KEY_PAGEUP else "power_down")
	elif event.keycode == KEY_H:
		toggle_hold_position()
	elif event.keycode == KEY_A:
		toggle_alpha_strike()
	elif event.keycode == KEY_E:
		select_visible(event.shift_pressed)
	elif event.keycode >= KEY_0 and event.keycode <= KEY_9:
		var n := int(event.keycode - KEY_0)
		if event.ctrl_pressed:
			assign_group(n)
		else:
			select_group(n, event.shift_pressed)
	else:
		return
	get_viewport().set_input_as_handled()


func _input(event: InputEvent) -> void:
	# A mode key's release disarms it wherever the focus is (the release functions).
	if event is InputEventKey and not event.pressed and _held.has(event.keycode):
		hold_mode_key(event.keycode, false)
	if event is InputEventKey and not event.pressed and event.keycode == WAYPOINT_KEY:
		run_waypoints()


## The waypoint key released: every unit given waypoints starts on them (setExecutingQueue +
## executeTacOrderQueue, missiongui.cpp:1703-1722).
func run_waypoints() -> void:
	for m in _queued:
		if not m.order_queue.is_empty():
			m.queue_running = true
	_queued.clear()


func _waypointing() -> bool:
	return Input.is_key_pressed(WAYPOINT_KEY)


# --- order modes --------------------------------------------------------------

func mode_on(kind: String) -> bool:
	if kind == "fire_from_position":
		return fire_from_position or _held.values().has(kind)
	if kind == "hold":
		return not selection.is_empty() and selection.all(func(m): return m.hold_position)
	if kind == "lay_mines":
		return lay_mines
	if kind == "suppress":
		return suppress
	if kind == "force_fire":
		return force_fire or _held.values().has(kind)
	if kind in AIMS or kind == "eject":
		return _held.values().has(kind)
	if kind in RANGES:
		return attack_range_mode() == kind
	var bit: int = MODE_BITS.get(kind, 0)
	return bit != 0 and (mode_bits & bit != 0 or _held.values().has(kind))


## A palette button: toggleDefaultSpeed / toggleGuard / toggleJump / toggleFireFromCurrentPos
## (controlGui.cpp:1340-1395, 1704). Jump needs every selected unit to have jump jets
## (MissionInterfaceManager::jump, missiongui.cpp:1941); returns false when refused.
func toggle_mode(kind: String) -> bool:
	match kind:
		"run":
			mode_bits = (mode_bits ^ RUN) & (RUN | GUARD)
		"guard":
			mode_bits = (mode_bits ^ GUARD) & (GUARD | RUN)  # "can run and guard"
		"jump":
			if mode_bits & JUMP == 0 and not can_jump():
				world.events.append({"type": "order_refused", "order": "jump", "why": "no_jump_jets"})
				return false
			mode_bits = (mode_bits ^ JUMP) & JUMP
		"fire_from_position":
			fire_from_position = not fire_from_position
		"short", "medium", "long":
			range_mode = "" if range_mode == kind else kind  # the range buttons are a radio group
		"force_fire":
			force_fire = not force_fire
		"suppress":
			# un-pressing clears suppression on all the player's immobile units (controlGui.cpp:2205-2228)
			if suppress:
				suppress = false
				for u in world.units:
					if u.team == player_team and u.is_mover() and u.run_speed <= 0.0 and u.suppression:
						u.suppression = false
						if u.order == SimWorld.Order.ATTACK_POINT:
							world.order_hold(u)
				return true
			if not selection.any(func(m): return m.is_mover() and m.run_speed <= 0.0 and m.num_weapons > 0):
				world.events.append({"type": "order_refused", "order": "suppress", "why": "no_artillery"})
				return false
			suppress = true
		"lay_mines":
			if not lay_mines and not selection.any(func(m): return m is SimVehicle and m.mine_stock > 0):
				world.events.append({"type": "order_refused", "order": "lay_mines", "why": "no_minelayer"})
				return false
			lay_mines = not lay_mines
		_:
			return false
	return true


## The attack range for the next attack: a held S/M/L key, else the range button, else optimal.
func attack_range_mode() -> String:
	for k in RANGES:
		if _held.values().has(k):
			return k
	return range_mode


## A mode key pressed (arms while held) or released (disarms).
func hold_mode_key(key: int, down: bool) -> void:
	var kind: String = MODE_KEYS.get(key, "")
	if kind == "":
		return
	if not down:
		_held.erase(key)
		return
	if kind == "jump" and not can_jump():
		world.events.append({"type": "order_refused", "order": "jump", "why": "no_jump_jets"})
		return
	if kind == "jump":
		mode_bits = 0  # jump is alone (toggleJump)
	elif kind != "fire_from_position" and not (kind in RANGES) and not (kind in AIMS) and not (kind in ["force_fire", "eject"]):
		mode_bits &= ~JUMP
	_held[key] = kind


## Every selected unit has jump jets (MissionInterfaceManager::canJump, missiongui.cpp:3467).
func can_jump() -> bool:
	return not selection.is_empty() and selection.all(func(m): return m.can_jump())


## setDefaultSpeed (controlGui.cpp:1367): an order used the palette mode.
func _used_mode() -> void:
	mode_bits = 0


## Stop (button or Backspace): TACTICAL_ORDER_STOP to the selection, and the palette back to
## its default (ControlGui::doStop, controlGui.cpp:1662-1701).
func stop() -> void:
	for m in selection:
		_order(m, "stop")
	mode_bits = 0
	fire_from_position = false


## Hold position (button or H): on for the whole selection unless all of it holds already
## (toggleHoldPosition, controlGui.cpp:2895-2924). A unit setting, not an order: it lasts until
## toggled, and the unit then moves only on a move order.
func toggle_hold_position() -> void:
	var on := not mode_on("hold")
	for m in selection:
		m.hold_position = on


## Ctrl+n: group n becomes exactly the current selection (makeForceGroup).
func assign_group(n: int) -> void:
	groups[n] = selection.duplicate()
	groups_changed.emit(groups)


## Live members of group n.
func group_units(n: int) -> Array[SimUnit]:
	var out: Array[SimUnit] = []
	for u in groups.get(n, []):
		if not u.is_disabled() and u.on_gui:
			out.append(u)
	return out


## The groups a unit belongs to (a unit may be in several, as in the original).
func groups_of(u: SimUnit) -> Array[int]:
	var out: Array[int] = []
	for n in groups:
		if groups[n].has(u):
			out.append(n)
	return out


## n: select group n alone; Shift+n adds it, or deselects it if it is all selected already (selectForceGroup).
func select_group(n: int, add: bool) -> void:
	var members := group_units(n)
	if not add:
		_set_selection(members)
		return
	var s: Array[SimUnit] = selection.duplicate()
	if not members.is_empty() and members.all(func(u): return s.has(u)):
		s.assign(s.filter(func(u): return not members.has(u)))
	else:
		for u in members:
			if not s.has(u):
				s.append(u)
	_set_selection(s)


## E / Shift+E: every own unit on screen.
func select_visible(add: bool) -> void:
	_select_box(get_viewport().get_visible_rect(), add)


func _double_click(screen: Vector2) -> void:
	var m := mech_at(screen, player_team)
	if m == null:
		return
	var s: Array[SimUnit] = [m]
	for n in groups_of(m):
		for u in group_units(n):
			if not s.has(u):
				s.append(u)
	_set_selection(s)
	if camera is RtsCamera:
		(camera as RtsCamera).follow(m)


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
	var s: Array[SimUnit] = []
	if add:
		s.assign(selection)
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


## A right-click order, as the right-button profile (missiongui.cpp:1503-1560): guard
## armed -> guard the thing clicked or the ground point; jump armed -> jump there (doMove ->
## doJump); a capturable target -> capture; an enemy -> attack (from the current position when
## that mode is on or the unit holds position); else move, walking unless Run is armed.
func _command(screen: Vector2) -> void:
	if selection.is_empty():
		return
	if mode_on("jump") and not can_jump():
		mode_bits &= ~JUMP  # the selection changed under an armed jump (missiongui.cpp:1291)
		_held.erase(KEY_J)
	# A selected repair truck services the damaged friendly mech clicked (support-powers.md 3.4).
	var trucks := selection.filter(func(u): return u.refit_pool > 0.0)
	if support and not trucks.is_empty():
		var friend := mech_at(screen, player_team)
		if friend is SimMech:
			for t in trucks:
				support.order_repair(t, friend)
			return
	var run := mode_on("run")
	var target := mech_at(screen)
	for aim_kind in AIMS:
		if mode_on(aim_kind):
			_aimed(target, aim_kind, run)
			return
	if mode_on("eject"):
		var own := mech_at(screen, player_team)
		if own is SimMech and own.commander == 0:
			_order(own, "eject")
		return
	if suppress:
		# doGuardTower (missiongui.cpp:5480-5508): suppressionFire on the selected units and an attack
		# point from where they stand (FIRERANGE_CURRENT, no pursue); the button stays pressed
		var sp = ground_at(screen)
		if sp == null:
			return
		for m in selection:
			if m.is_mover() and m.run_speed <= 0.0 and m.num_weapons > 0:
				_order(m, "attack_point", sp, {"pursue": false, "suppression": true})
		return
	if mode_on("force_fire"):
		# forceShot (missiongui.cpp:3208-3240): attack whatever is under the cursor, a friend or a
		# building included, else the ground point (TACTICAL_ORDER_ATTACK_POINT); firing from the
		# current position when that is armed.
		var ffp_f := mode_on("fire_from_position")
		var hit: SimUnit = target if target and not selection.has(target) else structure_at(screen)
		if hit:
			for m in selection:
				_order(m, "attack", hit, {"run": run, "pursue": not (ffp_f or m.hold_position), "force": true,
					"range": attack_range_mode()})
		else:
			var gp = ground_at(screen)
			if gp == null:
				return
			for m in selection:
				_order(m, "attack_point", gp, {"run": run, "pursue": not (ffp_f or m.hold_position)})
		force_fire = false
		fire_from_position = false
		return
	if mode_on("guard"):
		if target == null:
			target = structure_at(screen)
		var at = target if target else ground_at(screen)
		if at == null:
			return
		for m in selection:
			_order(m, "guard", at, {"run": run})
		_used_mode()
		return
	var enemy := target
	if enemy == null or enemy.team == player_team:
		enemy = structure_at(screen)
	# A friendly repair bay with a damaged mech selected: get fixed (missiongui.cpp:1417, doRepairBay
	# 4549-4566; support-powers.md 3.7). One mech pairs with the bay at a time.
	if enemy is SimStructure and enemy.team == player_team and enemy.can_refit and enemy.mech_bay and support:
		var sent := false
		for m in selection:
			if not sent and support.order_bay_repair(m, enemy):
				sent = true
		if sent:
			return
	# A capturable target always means capture (capture-and-objectives.md A2); only an
	# all-mech selection may capture, otherwise the click is refused.
	if enemy and abl and abl.can_capture(enemy, player_team):
		if selection.all(func(m): return m is SimMech):
			for m in selection:
				_order(m, "capture", enemy, {"run": run})
		else:
			world.events.append({"type": "capture_refused", "unit": selection[0].id, "target": enemy.id})
		return
	if enemy and enemy.team != player_team:
		var ffp := mode_on("fire_from_position")
		for m in selection:
			_order(m, "attack", enemy, {"run": run, "pursue": not (ffp or m.hold_position), "range": attack_range_mode()})
		fire_from_position = false
		return
	var g = ground_at(screen)
	if g == null:
		return
	if mode_on("jump"):
		# doJump: every selected unit must reach it (canJumpToWPos); else the click is refused.
		var why := ""
		for m in selection:
			why = world.jump_refusal(m, g)
			if why != "":
				break
		if why != "":
			world.events.append({"type": "order_refused", "unit": selection[0].id, "order": "jump", "why": why})
			return
		for m in selection:
			_order(m, "jump", g)
		_used_mode()
		return
	# One goal cell each around the click (MoverGroup::calcMoveGoals, missiongui.cpp:2473-2496),
	# handed out in selection order.
	var n := selection.size()
	var goals: Array = world.group_move_goals(g, n, selection.all(func(m): return m.hover))
	for i in n:
		var at: Vector2 = goals[i] if i < goals.size() else g
		if mode_on("lay_mines") and support and selection[i] is SimVehicle and selection[i].mine_stock > 0:
			support.order_lay_mines(selection[i], at, run)  # MOVE_MODE_MINELAYING
			continue
		_order(selection[i], "move", at, {"run": run})
	_used_mode()


## An aimed shot at an enemy ground 'Mech: the legs or arms take the left one unless it is gone,
## the head is refused once destroyed (missiongui.cpp:2109-2265); every selected unit attacks it
## aiming there. Refused (mState_DONT) on anything else.
func _aimed(target: SimUnit, kind: String, run: bool) -> void:
	if not (target is SimMech) or target.team == player_team or target.flying or target.is_disabled():
		world.events.append({"type": "order_refused", "order": kind, "why": "not_a_mech"})
		return
	var t: SimMech = target
	var B := SimMech.Body
	var gone := func(b: int) -> bool: return t.damage_state[b] == SimMech.DamageState.DESTROYED
	var loc := -1
	match kind:
		"aim_leg":
			if not (gone.call(B.LLEG) and gone.call(B.RLEG)):
				loc = B.RLEG if gone.call(B.LLEG) else B.LLEG
		"aim_arm":
			if not (gone.call(B.LARM) and gone.call(B.RARM)):
				loc = B.RARM if gone.call(B.LARM) else B.LARM
		"aim_head":
			if not gone.call(B.HEAD):
				loc = B.HEAD
	if loc < 0:
		world.events.append({"type": "order_refused", "order": kind, "why": "location_destroyed"})
		return
	var ffp := mode_on("fire_from_position")
	for m in selection:
		_order(m, "attack", t, {"run": run, "pursue": not (ffp or m.hold_position), "aim": loc})


## Player orders go through the unit's pbrain (SimAbl) when it has one, as in the
## original; otherwise straight to the world.
func _order(m: SimUnit, kind: String, arg: Variant = null, opts: Dictionary = {}) -> void:
	if _waypointing() and kind in ["move", "jump", "attack", "attack_point", "capture", "guard"]:
		# addQueuedTacOrder (warrior.cpp:1555-1590); up to 16 (MAX_QUEUED_TACORDERS_PER_WARRIOR)
		if m.order_queue.size() < 16:
			m.order_queue.append(func(): _order_now(m, kind, arg, opts))
			m.queue_running = false
			if not _queued.has(m):
				_queued.append(m)
			world.events.append({"type": "waypoint", "unit": m.id, "at": arg if arg is Vector2 else (arg as SimUnit).position,
				"kind": kind, "run": bool(opts.get("run", false))})
		return
	m.order_queue.clear()  # a direct order clears the queue (clearTacOrderQueue)
	m.queue_running = false
	_order_now(m, kind, arg, opts)


func _order_now(m: SimUnit, kind: String, arg: Variant = null, opts: Dictionary = {}) -> void:
	if abl and m.brain is SimAbl.Pilot:
		abl.player_order(m, kind, arg, opts)
		return
	var run: bool = opts.get("run", false)
	match kind:
		"attack":
			world.order_attack(m, arg, run, opts.get("pursue", true) and not m.hold_position,
				String(opts.get("range", "")), bool(opts.get("force", false)))
		"attack_point":
			world.order_attack_point(m, arg, run, opts.get("pursue", true) and not m.hold_position,
				bool(opts.get("suppression", false)))
		"move", "capture":
			world.order_move(m, arg if arg is Vector2 else (arg as SimUnit).position, run)
		"jump":
			world.order_jump(m, arg)
		"guard":
			if arg is SimUnit:
				world.order_guard(m, (arg as SimUnit).position, arg, true)
			else:
				world.order_guard(m, arg, null, true)
		_:
			world.order_stop(m)


func _set_selection(s: Array) -> void:
	for m in selection:
		if views.has(m.id):
			views[m.id].selected = false
	selection.assign(s)
	for m in selection:
		views[m.id].selected = true
	selection_changed.emit(selection)
