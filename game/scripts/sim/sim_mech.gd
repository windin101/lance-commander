class_name SimMech
extends SimUnit
## State of one BattleMech in the simulation, built the way BattleMech::init
## (mech.cpp:1373) builds it from the chassis CSV variant.

enum Body { HEAD, CTORSO, LTORSO, RTORSO, LARM, RARM, LLEG, RLEG }
enum Armor { HEAD, CTORSO, LTORSO, RTORSO, LARM, RARM, LLEG, RLEG, RCTORSO, RLTORSO, RRTORSO }
enum DamageState { NONE, PARTIAL, DESTROYED }

const BODY_KEYS := ["head", "ctorso", "ltorso", "rtorso", "larm", "rarm", "lleg", "rleg"]
const ARMOR_KEYS := BODY_KEYS + ["rctorso", "rltorso", "rrtorso"]
const ARMOR_TO_BODY := [0, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3]
const ARMOR_POINTS_PER_PLATE := 32.0
# Share of each armour plate per armour location (mech.cpp:285-295).
const PLATE_SHARE := [0.0, 0.17, 0.125, 0.125, 0.12, 0.12, 0.13, 0.13, 0.03, 0.02, 0.02]

var variant_name := ""
var loadout: Dictionary = {}  # campaign loadout {name, parts} when spawned from one (Mech Lab)

var internal: Array[float] = []  # current, per body location
var max_internal: Array[float] = []
var damage_state: Array[int] = []

## Crit spaces per body location: inventory index, or -1 for a free space.
var crit_spaces: Array = []
var crit_hit: Array = []  # parallel to crit_spaces: slot already hit
var total_spaces: Array[int] = []

var cockpit := -1
var engine := -1
var gyro := -1
var life_support := -1
var hip_actuators: Array[int] = []

var fallen := false
var failed_piloting_check := false
var damage_after_disabled := 0.0
var ct_first_injured_time := -1.0
var engine_blow_time := -1.0
var fall_time := -1.0

## lo: a campaign loadout (Loadout.to_sim: name, parts, items, crit_slots, armor_plates)
## that replaces the variant's own items, crit slots and plating; the variant still gives
## internal structure and armour.
static func from_chassis(chassis: Dictionary, variant_index: int, rules: SimRules, mech_pilot: SimPilot, lo: Dictionary = {}) -> SimMech:
	var m := SimMech.new()
	var variant: Dictionary = chassis["variants"][variant_index]
	if lo.has("items") and lo.has("crit_slots"):
		var v := variant.duplicate()
		v["items"] = lo["items"]
		v["crit_slots"] = lo["crit_slots"]
		v["armor_plates"] = int(lo.get("armor_plates", variant.get("armor_plates", 0)))
		v["name"] = String(lo.get("name", variant["name"]))
		variant = v
		m.loadout = {"name": v["name"], "parts": lo.get("parts", {})}
	m.name = chassis["name"]
	m.variant_name = variant["name"]
	m.tonnage = chassis["tonnage"]
	m.pilot = mech_pilot if mech_pilot else SimPilot.new()
	m.heat_capacity = max(1.0, float(chassis.get("heat_index", 30)))
	m.run_speed = float(chassis.get("max_run_speed", 20))
	m.walk_speed = m.run_speed * 0.52
	m.max_torso_yaw = float(chassis.get("max_torso_yaw", 120))
	m.turret_rate = float(chassis.get("torso_yaw_rate", 360))
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


func can_jump() -> bool:
	return items.any(func(it): return it["form"] == "JumpJet")


## BattleMech::getJumpRange (mech.cpp:6684): numJumpJets (5) plus one for a LongJump
## pilot, times worldUnitsPerVertex (128 wu = one 25.6 m vertex).
func jump_range() -> float:
	if not can_jump():
		return 0.0
	var jets := 5 + (1 if pilot and pilot.specialties.has("LongJump") else 0)
	return jets * 25.6


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


func kind() -> String:
	return "mech"
