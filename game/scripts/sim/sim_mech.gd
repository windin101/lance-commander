class_name SimMech
extends RefCounted
## State of one BattleMech in the simulation, built the way BattleMech::init
## (mech.cpp:1373) builds it from the chassis CSV variant.

enum Body { HEAD, CTORSO, LTORSO, RTORSO, LARM, RARM, LLEG, RLEG }
enum Armor { HEAD, CTORSO, LTORSO, RTORSO, LARM, RARM, LLEG, RLEG, RCTORSO, RLTORSO, RRTORSO }
enum DamageState { NONE, PARTIAL, DESTROYED }
enum Status { NORMAL, SHUTDOWN, DISABLED, DESTROYED }
# Body states index gamesys BodyStateHeat (mech.cpp NUM_MECH_STATES order).
enum BodyState { PARKED, STANDING, WALKING, RUNNING, REVERSE, LIMPING, JUMPING, FALLEN_FORWARD, FALLEN_BACKWARD }

const BODY_KEYS := ["head", "ctorso", "ltorso", "rtorso", "larm", "rarm", "lleg", "rleg"]
const ARMOR_KEYS := BODY_KEYS + ["rctorso", "rltorso", "rrtorso"]
const ARMOR_TO_BODY := [0, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3]
const ARMOR_POINTS_PER_PLATE := 32.0
# Share of each armour plate per armour location (mech.cpp:285-295).
const PLATE_SHARE := [0.0, 0.17, 0.125, 0.125, 0.12, 0.12, 0.13, 0.13, 0.03, 0.02, 0.02]
const OTHER_FORMS := ["JumpJet", "Cockpit", "Sensors", "LifeSupport", "Gyroscope", "PowerAmplifier",
	"ECM", "Probe", "Jammer", "Case", "Actuator", "Engine", "HeatSink"]
const WEAPON_FORMS := ["Weapon", "EnergyWeapon", "BallisticWeapon", "MissileWeapon"]

var id := -1
var name := ""
var variant_name := ""
var model := ""  # appearance name, e.g. "bushwacker"
var paint: Array = []  # mission ARGB ints: highlight1, highlight2, base
var tonnage := 0.0
var team := 0
var is_player := false
var pilot: SimPilot

var position := Vector2.ZERO  # metres; x east, y north
var facing := 0.0  # degrees, 0 = north, clockwise positive
var body_state: int = BodyState.STANDING

var armor: Array[float] = []  # current, per armour location
var max_armor: Array[float] = []
var internal: Array[float] = []  # current, per body location
var max_internal: Array[float] = []
var damage_state: Array[int] = []

## Inventory items: {component, form, health, disabled, amount, ready_time, body_location}
var items: Array[Dictionary] = []
var num_other := 0
var num_weapons := 0
var num_ammo := 0
## Crit spaces per body location: inventory index, or -1 for a free space.
var crit_spaces: Array = []
var crit_hit: Array = []  # parallel to crit_spaces: slot already hit
var total_spaces: Array[int] = []

var cockpit := -1
var engine := -1
var gyro := -1
var life_support := -1
var hip_actuators: Array[int] = []

var status: int = Status.NORMAL
var fallen := false
var failed_piloting_check := false
var damage_after_disabled := 0.0
var ct_first_injured_time := -1.0
var engine_blow_time := -1.0

var heat := 0.0
var heat_capacity := 30.0
var heat_check_time := 0.0

# Movement and orders (SimWorld).
var run_speed := 20.0  # m/s, chassis MaxRunSpeed
var walk_speed := 10.0  # m/s, walk gesture end velocity
var max_torso_yaw := 120.0
var speed := 0.0
var prev_position := Vector2.ZERO
var prev_facing := 0.0
var order: int = 0
var order_target: SimMech = null
var current_target: SimMech = null
var path := PackedVector2Array()
var path_index := 0
var repath_time := 0.0
var fall_time := -1.0
var reported_disabled := false


static func from_chassis(chassis: Dictionary, variant_index: int, rules: SimRules, mech_pilot: SimPilot) -> SimMech:
	var m := SimMech.new()
	var variant: Dictionary = chassis["variants"][variant_index]
	m.name = chassis["name"]
	m.variant_name = variant["name"]
	m.tonnage = chassis["tonnage"]
	m.pilot = mech_pilot if mech_pilot else SimPilot.new()
	m.heat_capacity = max(1.0, float(chassis.get("heat_index", 30)))
	m.run_speed = float(chassis.get("max_run_speed", 20))
	m.walk_speed = m.run_speed * 0.52
	m.max_torso_yaw = float(chassis.get("max_torso_yaw", 120))
	for key in BODY_KEYS:
		m.max_internal.append(float(chassis["max_internal"][key]))
		m.internal.append(float(variant["internal"][key]))
		m.damage_state.append(DamageState.NONE)
	var plates := int(variant.get("armor_plates", 0))
	for i in ARMOR_KEYS.size():
		var base := float(chassis["base_armor"][ARMOR_KEYS[i]])
		var total: float = base + PLATE_SHARE[i] * ARMOR_POINTS_PER_PLATE * plates
		m.max_armor.append(total)
		m.armor.append(total if plates > 0 else float(variant["armor"][ARMOR_KEYS[i]]))
	m._build_inventory(variant, rules)
	for loc in Body.size():
		m._update_damage_state(loc)
	return m


func _build_inventory(variant: Dictionary, rules: SimRules) -> void:
	var item_ids: Array = variant["items"]
	var item_to_inv := {}
	# Three passes, as the original: other components, weapons, then ammo.
	for pass_forms in [OTHER_FORMS, WEAPON_FORMS, ["Ammo"]]:
		for item_number in item_ids.size():
			var cid = item_ids[item_number]
			if cid == null:
				continue
			var comp := rules.component(int(cid))
			if comp.is_empty() or not (comp["form"] in pass_forms):
				continue
			var item := {
				"component": comp, "form": comp["form"], "master_id": int(cid),
				"health": 1, "disabled": false, "amount": 1,
				"ready_time": 0.0, "body_location": -1,
			}
			if comp["form"] == "Ammo":
				item["amount"] = int(comp["ammo"]["per_ton"])
			item_to_inv[item_number] = items.size()
			items.append(item)
	for it in items:
		match it["form"]:
			"Ammo": num_ammo += 1
			"Weapon", "EnergyWeapon", "BallisticWeapon", "MissileWeapon": num_weapons += 1
			_: num_other += 1
	for loc in Body.size():
		var spaces: Array[int] = []
		var hits: Array[bool] = []
		var occupied := 0
		for slot in variant["crit_slots"][BODY_KEYS[loc]]:
			var inv: int = item_to_inv.get(int(slot), -1) if slot != null else -1
			spaces.append(inv)
			hits.append(false)
			if inv >= 0:
				items[inv]["body_location"] = loc
				occupied += int(items[inv]["component"]["crits"])
				_note_key_component(inv, loc)
		crit_spaces.append(spaces)
		crit_hit.append(hits)
		total_spaces.append(occupied)


func _note_key_component(inv: int, loc: int) -> void:
	match items[inv]["form"]:
		"Cockpit": cockpit = inv
		"Engine": engine = inv
		"Gyroscope": gyro = inv
		"LifeSupport": life_support = inv
		"Actuator":
			if (loc == Body.LLEG or loc == Body.RLEG) and items[inv]["component"]["name"].contains("Hip"):
				hip_actuators.append(inv)


func _update_damage_state(loc: int) -> void:
	if internal[loc] <= 0.0:
		damage_state[loc] = DamageState.DESTROYED
	elif internal[loc] / max_internal[loc] <= 0.5:
		damage_state[loc] = DamageState.PARTIAL
	else:
		damage_state[loc] = DamageState.NONE


func is_disabled() -> bool:
	return status == Status.DISABLED or status == Status.DESTROYED


func is_destroyed() -> bool:
	return status == Status.DESTROYED


func is_weapon(inv: int) -> bool:
	return inv >= num_other and inv < num_other + num_weapons


func weapon_indices() -> Array[int]:
	var out: Array[int] = []
	for i in range(num_other, num_other + num_weapons):
		out.append(i)
	return out


func weapon(inv: int) -> Dictionary:
	return items[inv]["component"].get("weapon", {})


func uses_ammo(inv: int) -> bool:
	return weapon(inv).get("ammo_type", "none") != "none"


## Rounds left for a weapon's ammo type, or -1 for unlimited (getWeaponShots).
func weapon_shots(inv: int) -> int:
	if not uses_ammo(inv):
		return -1
	var ammo_id := int(weapon(inv)["ammo_id"])
	var total := 0
	for i in range(num_other + num_weapons, items.size()):
		if items[i]["master_id"] == ammo_id:
			total += int(items[i]["amount"])
	return total


## Spend rounds from the first bins with ammo (Mover::reduceAmmo).
func reduce_ammo(ammo_id: int, amount: int) -> void:
	for i in range(num_other + num_weapons, items.size()):
		if items[i]["master_id"] != ammo_id:
			continue
		if items[i]["amount"] > amount:
			items[i]["amount"] -= amount
			return
		amount -= items[i]["amount"]
		items[i]["amount"] = 0


func is_weapon_ready(inv: int, now: float) -> bool:
	return not items[inv]["disabled"] and items[inv]["ready_time"] <= now


## Signed angle from this mech's facing to a point: negative = counter-clockwise
## (left), as GameObject::relFacingTo (gameobj.cpp:1605).
func rel_facing_to(point: Vector2) -> float:
	var f := Vector2(sin(deg_to_rad(facing)), cos(deg_to_rad(facing)))
	var g := point - position
	if g.length_squared() == 0.0:
		return 0.0
	var angle := rad_to_deg(f.angle_to(g))  # positive = counter-clockwise in x-east/y-north
	return -angle


func distance_to(other_position: Vector2) -> float:
	return position.distance_to(other_position)


func heat_level() -> int:
	return clampi(int(floor(30.0 * heat / heat_capacity)), 0, 30)
