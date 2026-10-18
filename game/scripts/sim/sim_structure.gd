class_name SimStructure
extends SimUnit
## A building or other destructible map object (bldng.cpp Building::handleWeaponHit):
## damage accumulates until it reaches the type's DmgLevel, then it is destroyed.
## Shots at structures always hit (mover.cpp:6255).

var object_type := -1
var object_index := -1  # index in data/maps/<mission>/objects.json
var damage_level := 1.0
var damage := 0.0
var extent_m := 0.0


func _init() -> void:
	uses_heat = false


func kind() -> String:
	return "structure"


func is_mover() -> bool:
	return false


func roll_hit_location(_rules: SimRules, _rng: SimRng, _from: Vector2) -> int:
	return 0


func take_hit(_rules: SimRules, _rng: SimRng, amount: float, _location: int, _master_id: int, _now: float) -> void:
	if is_destroyed() or amount <= 0.0:
		return
	damage = minf(damage + amount, damage_level)
	if damage >= damage_level:
		status = Status.DESTROYED
