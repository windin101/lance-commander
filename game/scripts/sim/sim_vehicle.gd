class_name SimVehicle
extends SimUnit
## A ground vehicle (Code/gvehicl.cpp). Five sections, each with armour and
## internal structure; damage past a section's armour goes into that section's
## internal structure, and losing any section destroys the vehicle. No transfer,
## no crits (the CriticalHitTable is loaded but never used), no ammo explosions.

enum Section { FRONT, LEFT, RIGHT, REAR, TURRET }
const SECTION_KEYS := ["front", "left", "right", "rear", "turret"]
const WALK_SPEED := 9.0  # gamesys GroundVehicle:Movement WalkSpeed
const FIRE_ARC_HALF := 12.5  # gamesys Mover:FireWeapon FireArc[1] / 2 (mover.cpp:1876)

var internal: Array[float] = []
var max_internal: Array[float] = []
var explosion_damage := 0.0
var explosion_radius_m := 0.0
var path_locks := true


func _init() -> void:
	uses_heat = false


func kind() -> String:
	return "vehicle"


## vehicleTurnRate by tonnage (gvehicl.cpp:159).
static func turn_rate_for(tons: float) -> float:
	if tons < 10: return 360.0
	if tons < 60: return 240.0
	if tons < 70: return 210.0
	if tons < 80: return 140.0
	if tons < 90: return 120.0
	return 90.0


static func from_data(v: Dictionary, rules: SimRules, vehicle_pilot: SimPilot) -> SimVehicle:
	var u := SimVehicle.new()
	u.name = String(v.get("name", "vehicle")).capitalize()
	u.model = String(v.get("appearance", ""))
	u.tonnage = float(v.get("tonnage", 10))
	u.pilot = vehicle_pilot if vehicle_pilot else SimPilot.new()
	u.hover = bool(v.get("hover", false))
	u.path_locks = bool(v.get("path_locks", true))
	u.run_speed = float(v.get("max_velocity", 10))
	u.walk_speed = minf(WALK_SPEED, u.run_speed)
	u.max_torso_yaw = float(v.get("max_turret_yaw", 0))
	u.fire_arc_half = FIRE_ARC_HALF
	u.turn_rate = turn_rate_for(u.tonnage)
	u.explosion_damage = float(v.get("explosion_damage", 0))
	u.explosion_radius_m = float(v.get("explosion_radius", 0)) * 0.2
	for key in SECTION_KEYS:
		u.max_armor.append(float(v["armor"][key]))
		u.armor.append(float(v["armor"][key]))
		u.max_internal.append(float(v["internal"][key]))
		u.internal.append(float(v["internal"][key]))
	for mid in v.get("items", []):
		var comp := rules.component(int(mid))
		if comp.is_empty():
			continue
		var item := {"component": comp, "form": comp["form"], "master_id": int(mid), "health": 1,
			"disabled": false, "amount": 1, "ready_time": 0.0, "body_location": -1}
		if comp["form"] == "Ammo":
			item["amount"] = int(comp["ammo"]["per_ton"])
			u.num_ammo += 1
		elif comp["form"] in WEAPON_FORMS:
			u.num_weapons += 1
		else:
			u.num_other += 1
		u.items.append(item)
	return u


## GroundVehicle::calcHitLocation (gvehicl.cpp:4037): turret on (d100+d100)/2 >= 70,
## otherwise by the attacker's bearing.
func roll_hit_location(_rules: SimRules, rng: SimRng, from: Vector2) -> int:
	var z := (rng.roll(100) + rng.roll(100)) / 2
	if z >= 70:
		return Section.TURRET
	var angle := rel_facing_to(from)
	if angle >= -45.0 and angle <= 45.0:
		return Section.FRONT
	if angle > -135.0 and angle < -45.0:
		return Section.LEFT
	if angle > 45.0 and angle < 135.0:
		return Section.RIGHT
	return Section.REAR


## GroundVehicle::handleWeaponHit (gvehicl.cpp:4289).
func take_hit(_rules: SimRules, _rng: SimRng, amount: float, location: int, _master_id: int, _now: float) -> void:
	if is_destroyed() or amount <= 0.0 or location < 0 or location >= armor.size():
		return
	if armor[location] > 0.0:
		if amount > armor[location]:
			amount -= armor[location]
			armor[location] = 0.0
		else:
			armor[location] -= amount
			return
	if amount >= internal[location]:
		internal[location] = 0.0
		status = Status.DESTROYED
	else:
		internal[location] -= amount
