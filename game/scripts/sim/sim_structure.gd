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
var parent: SimStructure = null  # control building (turret.cpp:551, bldng.cpp:878-890)
var control := false  # parent of turrets: a capturable control building (objmgr.cpp:970-981)
var tower_sensor_m := -1.0  # a team sensor (sensor towers), metres (bldng.cpp:1266)
var explosion_damage := 0.0  # BuildingData ExplosionDamage: its blast when destroyed (bldng.cpp:205-211, 1476-1488)
var explosion_radius_m := 0.0
var can_refit := false  # CanRefit (repair bay pool = DmgLevel - damage, bldng.h:372)
var mech_bay := false  # MechBay: repairs mechs (tacordr.cpp:1087)
var refit_buddy: SimUnit = null  # the unit being repaired here (refitBuddyWID)
var sight_radius_m := -1.0  # its appearance radius for line of sight (SimWorld.sight_radius), -1 not yet


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


## The tower's sensor works: it stands and its control building (if any) does too
## (bldng.cpp:878-885: a destroyed parent disables and breaks the sensor).
func sensor_works() -> bool:
	if tower_sensor_m <= 0.0 or is_destroyed() or team < 0:
		return false
	return parent == null or not parent.is_destroyed()
