class_name SimBrain
extends RefCounted
## The player lance's brain (pbrain.abl's return-fire behaviour), configured from
## data/brains/<mission>.json "PBrain". Every other unit runs its mission's original
## ABL brain through SimAbl; player units keep this one until player orders reach the
## ABL tactical-order state.
##
## Being shot at (PILOT_EVENT_TARGETED): with no order, attack the shooter
## (pbrain.abl l.170); while moving, fire at it on the move. Call help from player
## allies within help_m, at most every 20 s.

var cfg: Dictionary
var _handled_attack_time := -1.0
var _help_time := -100.0


static func create(config: Dictionary, _unit: SimUnit) -> SimBrain:
	var b := SimBrain.new()
	b.cfg = config
	return b


func think(world: SimWorld, u: SimUnit) -> void:
	var shooter: SimUnit = u.last_attacker
	if shooter == null or u.last_attacked_time <= _handled_attack_time:
		return
	_handled_attack_time = u.last_attacked_time
	if shooter.is_disabled():
		return
	if u.order == SimWorld.Order.HOLD:
		world.order_attack(u, shooter)
	elif u.current_target == null:
		u.current_target = shooter
	var help_m := float(cfg.get("help_m", 0.0))
	if help_m > 0.0 and world.time - _help_time >= 20.0:
		_help_time = world.time
		for ally in world.units:
			if ally != u and ally.team == u.team and not ally.is_disabled() and ally.brain is SimBrain \
					and ally.distance_to(u.position) <= help_m:
				ally.brain.help(world, ally, shooter)


func help(world: SimWorld, u: SimUnit, enemy: SimUnit) -> void:
	if u.order == SimWorld.Order.HOLD:
		world.order_attack(u, enemy)
