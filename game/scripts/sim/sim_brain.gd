class_name SimBrain
extends RefCounted
## Unit AI as a small state machine, configured per brain from
## data/brains/<mission>.json (transcribed from the mission's ABL brains).
##
## States follow corebrain.abx: guard (hold the start point, scan), patrol
## (walk the route, scan), idle / powered_down (do nothing until triggered),
## powerup (wait, then patrol), ambush (move to a point and hold, wider scan),
## attack (engage a target; on its death return to the previous state).
## Being shot at (PILOT_EVENT_TARGETED) makes an idle unit attack the shooter
## and may call allies within help radius.

const THINK_PERIOD := 0.5
const WORLD_UNIT_M := 0.2

var cfg: Dictionary
var state := "guard"
var prev_state := "guard"
var home := Vector2.ZERO
var patrol: PackedVector2Array = PackedVector2Array()
var patrol_index := 0
var patrol_dir := 1
var _patrol_issued := -1  # waypoint index the current move order heads for
var target: SimUnit = null
var _next_think := 0.0
var _powerup_at := -1.0
var _flanked := false
var _handled_attack_time := -1.0
var _help_time := -100.0


static func create(config: Dictionary, unit: SimUnit) -> SimBrain:
	var b := SimBrain.new()
	b.cfg = config
	b.home = unit.position
	for p in config.get("patrol", []):
		b.patrol.append(Vector2(float(p[0]), float(p[1])) * WORLD_UNIT_M)
	b.state = String(config.get("start", "guard"))
	if config.get("player", false):
		b.state = "player"
	if b.state == "powered_down" and unit is SimMech:
		unit.status = SimUnit.Status.SHUTDOWN
		unit.powered_down = true
	b.prev_state = b.state
	return b


func think(world: SimWorld, u: SimUnit) -> void:
	_react_to_fire(world, u)
	if world.time < _next_think:
		return
	_next_think = world.time + THINK_PERIOD
	var trigger := String(cfg.get("trigger", ""))
	if trigger != "" and world.flags.get(trigger, false) and state in ["guard", "idle", "powered_down"]:
		_enter(world, u, String(cfg.get("on_trigger", "patrol")))
	match state:
		"player":
			pass  # orders come from the player; return fire is handled in _react_to_fire
		"guard":
			if not _scan(world, u, float(cfg.get("acquire_m", 300))) and u.distance_to(home) > 25.0 and u.order == SimWorld.Order.HOLD:
				world.order_move(u, home)
		"patrol":
			if not _scan(world, u, float(cfg.get("acquire_m", 300))):
				_patrol_step(world, u)
		"powerup":
			if world.time >= _powerup_at:
				if u.powered_down:
					u.powered_down = false
					u.status = SimUnit.Status.NORMAL
				_enter(world, u, "patrol")
		"ambush":
			if not _scan(world, u, float(cfg.get("ambush_acquire_m", 150))):
				var p: Vector2 = Vector2(cfg["ambush_point"][0], cfg["ambush_point"][1]) * WORLD_UNIT_M
				if u.distance_to(p) > 15.0 and u.order == SimWorld.Order.HOLD:
					world.order_move(u, p)
		"attack":
			_attack_step(world, u)


func _enter(world: SimWorld, u: SimUnit, new_state: String) -> void:
	if new_state != "attack":
		prev_state = new_state
	state = new_state
	match new_state:
		"powerup":
			_powerup_at = world.time + float(cfg.get("powerup_delay", 0.0))
		"patrol":
			patrol_index = _nearest_patrol_point(u)
			if not patrol.is_empty():
				_patrol_issued = patrol_index
				world.order_move(u, patrol[patrol_index])
		"ambush":
			var p: Vector2 = Vector2(cfg["ambush_point"][0], cfg["ambush_point"][1]) * WORLD_UNIT_M
			world.order_move(u, p)


## Closest enemy mover within radius (setTargetPriority MOVER slot).
func _scan(world: SimWorld, u: SimUnit, radius_m: float) -> bool:
	var best: SimUnit = null
	var best_d := radius_m
	for e in world.enemies_of(u):
		var d := u.distance_to(e.position)
		if d <= best_d:
			best = e
			best_d = d
	if best:
		_attack(world, u, best)
		return true
	return false


func _attack(world: SimWorld, u: SimUnit, t: SimUnit) -> void:
	if state != "attack":
		prev_state = state if state != "player" else "player"
	target = t
	state = "attack" if not cfg.get("player", false) else "player"
	if cfg.has("attack_flag"):
		world.flags[String(cfg["attack_flag"])] = true  # e.g. Starslayer attack sets Bandits_Equipped_Trigger
	_flanked = false
	world.order_attack(u, t)


func _attack_step(world: SimWorld, u: SimUnit) -> void:
	if target == null or target.is_disabled() \
			or u.distance_to(target.position) > maxf(float(cfg.get("disengage_m", 125)), world.attack_range(u) / 0.9) * 2.0:
		target = null
		_enter(world, u, prev_state if prev_state != "attack" else "guard")
		return
	var tactic := String(cfg.get("tactic", ""))
	if tactic != "" and not _flanked and u.distance_to(target.position) <= world.attack_range(u):
		_flanked = true
		var offset := Vector2.ZERO
		var r := world.attack_range(u) * 0.7
		match tactic:
			"left_flank": offset = Vector2(r, 0)  # corebrain.abx:651 LEFT = east of the target
			"right_flank": offset = Vector2(-r, 0)
			"rear": offset = Vector2(0, r - 20.0)
		world.order_move(u, target.position + offset)
		return
	if u.order == SimWorld.Order.HOLD:
		world.order_attack(u, target)


func _patrol_step(world: SimWorld, u: SimUnit) -> void:
	if patrol.is_empty() or u.order != SimWorld.Order.HOLD:
		return
	# A finished move counts as arrival even if the point itself was unreachable
	# (the path ends at the nearest walkable cell).
	if _patrol_issued != patrol_index and u.distance_to(patrol[patrol_index]) > 20.0:
		_patrol_issued = patrol_index
		world.order_move(u, patrol[patrol_index])
		return
	if cfg.get("patrol_mode", "loop") == "linear":
		if patrol_index + patrol_dir < 0 or patrol_index + patrol_dir >= patrol.size():
			patrol_dir = -patrol_dir
		patrol_index += patrol_dir
	else:
		patrol_index = (patrol_index + 1) % patrol.size()
	_patrol_issued = patrol_index
	world.order_move(u, patrol[patrol_index])


func _nearest_patrol_point(u: SimUnit) -> int:
	var best := 0
	for i in patrol.size():
		if u.distance_to(patrol[i]) < u.distance_to(patrol[best]):
			best = i
	return best


## PILOT_EVENT_TARGETED: attack the shooter if not already engaged; call for help.
func _react_to_fire(world: SimWorld, u: SimUnit) -> void:
	var shooter: SimUnit = u.last_attacker
	if shooter == null or u.last_attacked_time <= _handled_attack_time:
		return
	_handled_attack_time = u.last_attacked_time
	if shooter.is_disabled():
		return
	if cfg.get("player", false):
		if u.order == SimWorld.Order.HOLD:
			world.order_attack(u, shooter)  # pbrain.abl l.170: no order -> attack the attacker
		elif u.current_target == null:
			u.current_target = shooter  # moving: fire while moving
	elif state != "attack":
		if u.powered_down:  # mc2_01_Starslayer.abl: targeted while shut down still attacks
			u.powered_down = false
			u.status = SimUnit.Status.NORMAL
		_attack(world, u, shooter)
	var help := float(cfg.get("help_m", 0.0))
	if help > 0.0 and world.time - _help_time >= 20.0:
		_help_time = world.time
		for ally in world.units:
			if ally == u or ally.team != u.team or ally.is_disabled() or ally.brain == null:
				continue
			if ally.distance_to(u.position) <= help:
				ally.brain.help(world, ally, shooter)


func help(world: SimWorld, u: SimUnit, enemy: SimUnit) -> void:
	if cfg.get("player", false):
		if u.order == SimWorld.Order.HOLD:
			world.order_attack(u, enemy)
	elif state != "attack" and state != "powered_down":
		_attack(world, u, enemy)
