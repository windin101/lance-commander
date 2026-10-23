class_name SimCombat
extends RefCounted
## Combat resolution, reimplemented from Mover::calcAttackChance,
## BattleMech::fireWeapon, calcHitLocation, handleWeaponHit, injureBodyLocation,
## calcCriticalHit, hitInventoryItem and destroyBodyLocation.
## Spec and source pointers: docs/specs/combat-rules.md.

const B := SimMech.Body
const A := SimMech.Armor
const NO_SHOT := -1.0


## Chance to hit (5-95), 100 for a disabled target, or NO_SHOT when out of range.
static func attack_chance(rules: SimRules, attacker: SimUnit, inv: int, target: SimUnit, aim_location: int = -1) -> float:
	var weapon := attacker.weapon(inv)
	var chance := attacker.pilot.gunnery
	var skills := rules.player_skills if (attacker.is_player or not rules.fix_enemy_difficulty) else rules.enemy_skills
	if attacker.is_player or rules.fix_enemy_difficulty:
		chance *= float(skills[rules.difficulty]) / 100.0

	var distance := attacker.distance_to(target.position)
	var span: Array = rules.weapon_ranges[rules.range_index(weapon["range"])]
	if distance <= float(span[0]) - SimRules.MAP_CELL_DIAGONAL:
		return NO_SHOT
	if distance > float(span[1]) + SimRules.MAP_CELL_DIAGONAL:
		return NO_SHOT

	if target.is_disabled() or not target.is_mover():
		return 100.0  # mover.cpp:6255: non-movers and disabled targets are always hit

	var tp: SimPilot = target.pilot if target.pilot else SimPilot.new()
	if not (target is SimMech):
		pass  # chassis specialties only matter against mechs
	elif target.tonnage < 40 and tp.has("LightMechSpecialist"):
		chance -= 30.0
	elif target.tonnage >= 40 and target.tonnage < 60 and tp.has("MediumMechSpecialist"):
		chance -= 20.0
	elif target.tonnage >= 60 and target.tonnage < 80 and tp.has("HevayMechSpecialist"):
		chance -= 10.0
	elif target.tonnage >= 80 and target.tonnage < 100 and tp.has("AssaultMechSpecialist"):
		chance -= 10.0

	var master_id := int(attacker.items[inv]["master_id"])
	for specialty in SimRules.WEAPON_SPECIALTIES:
		if attacker.pilot.has(specialty) and master_id in SimRules.WEAPON_SPECIALTIES[specialty]:
			chance += rules.weapon_specialist_modifier

	var unit := 1.0 if rules.fix_range_specialists else 5.01
	var p := attacker.pilot
	if distance <= 60.0 * unit and p.has("ShortRangeSpecialist"):
		chance += 15.0
	if distance >= 31.0 * unit and distance <= 120.0 * unit and p.has("MediumRangeSpecialist"):
		chance += 15.0
	if distance >= 61.0 * unit and distance <= 180.0 * unit and p.has("LongRangeSpecialist"):
		chance += 15.0

	if aim_location > -1 and target is SimMech:
		match aim_location:
			B.HEAD: chance *= rules.head_shot_modifier
			B.LARM, B.RARM: chance *= rules.arm_shot_modifier
			B.LLEG, B.RLEG: chance *= rules.leg_shot_modifier
		if p.has("SharpShooter"):
			chance += 20.0

	if attacker.uses_heat:
		# H3, softened by H9 (heat_fire_mod_factor, combat-rules.md)
		chance -= float(rules.heat_row(attacker.heat_level())["fire_mod"]) * rules.heat_fire_mod_factor
	return clampf(chance, 5.0, 95.0)


## Fire one weapon. Returns a shot: {fired, reason, chance, roll, hit,
## location, damage, master_id}. Damage is applied later with apply_shot()
## (the original applies it when the projectile lands).
static func fire_weapon(rules: SimRules, rng: SimRng, attacker: SimUnit, inv: int, target: SimUnit, now: float, aim_location: int = -1) -> Dictionary:
	var shot := {"fired": false, "reason": "", "chance": 0.0, "roll": -1, "hit": false,
		"location": -1, "damage": 0.0, "master_id": int(attacker.items[inv]["master_id"])}
	if attacker.status != SimUnit.Status.NORMAL:
		shot["reason"] = "not_operational"
		return shot
	if not attacker.is_weapon(inv) or not attacker.is_weapon_ready(inv, now):
		shot["reason"] = "not_ready"
		return shot
	if attacker.weapon_shots(inv) == 0:
		shot["reason"] = "no_ammo"
		return shot
	var chance := attack_chance(rules, attacker, inv, target, aim_location)
	if chance < 0.0:
		shot["reason"] = "out_of_range"
		return shot

	var weapon := attacker.weapon(inv)
	shot["fired"] = true
	shot["chance"] = chance
	var roll := rng.roll(100)
	shot["roll"] = roll
	attacker.items[inv]["ready_time"] = now + float(weapon["recycle"])
	if rules.heat_enabled and attacker.uses_heat:
		attacker.heat += float(weapon["heat"])

	var hit := roll < int(chance)
	if attacker.uses_ammo(inv) and (hit or not weapon.get("streak", false)):
		attacker.reduce_ammo(int(weapon["ammo_id"]), 1)
	if hit:
		shot["hit"] = true
		shot["damage"] = float(weapon["damage"])
		if aim_location > -1:
			shot["location"] = aim_location
		elif target is SimMech:
			shot["location"] = hit_location(rules, rng, target, attacker.position)
		else:
			shot["location"] = target.roll_hit_location(rules, rng, attacker.position)
	return shot


## Apply a shot's damage to its target (no-op for misses).
static func apply_shot(rules: SimRules, rng: SimRng, target: SimUnit, shot: Dictionary, now: float) -> void:
	if not shot.get("hit", false):
		return
	if target is SimMech:
		handle_weapon_hit(rules, rng, target, float(shot["damage"]), int(shot["location"]), int(shot["master_id"]), now)
	else:
		target.take_hit(rules, rng, float(shot["damage"]), int(shot["location"]), int(shot["master_id"]), now)


## Armour location hit, from the attacker's bearing (calcHitLocation).
static func hit_location(rules: SimRules, rng: SimRng, target: SimMech, attacker_position: Vector2, section: int = SimRules.Section.MIDDLE) -> int:
	var angle := target.rel_facing_to(attacker_position)
	var arc: int
	if angle >= -45.0 and angle <= 45.0:
		arc = SimRules.Arc.FRONT
	elif angle > -135.0 and angle < -45.0:
		arc = SimRules.Arc.LEFT
	elif angle > 45.0 and angle < 135.0:
		arc = SimRules.Arc.RIGHT
	else:
		arc = SimRules.Arc.REAR
	var roll := rng.roll(100)
	var weights := rules.hit_location_weights(section, arc)
	for loc in weights.size():
		if roll < int(weights[loc]):
			return loc
		roll -= int(weights[loc])
	return weights.size() - 1


static func is_ammo(rules: SimRules, master_id: int) -> bool:
	return rules.component(master_id).get("form", "") == "Ammo"


## BattleMech::handleWeaponHit. armor_loc is an armour location (0-10).
static func handle_weapon_hit(rules: SimRules, rng: SimRng, m: SimMech, damage: float, armor_loc: int, master_id: int, now: float) -> void:
	if damage <= 0.0 or armor_loc < 0 or m.is_destroyed():
		return
	if m.is_disabled() and m.fallen:
		m.damage_after_disabled += damage
		if m.damage_after_disabled > rules.destruct_damage:
			_destroy_mech(rules, rng, m, now)
		return

	var ammo_explosion := is_ammo(rules, master_id)
	var body: int = SimMech.ARMOR_TO_BODY[armor_loc]
	if body == B.HEAD and damage >= 2.0:
		_injure_pilot(m, 1.0)

	if m.armor[armor_loc] > 0.0 and not ammo_explosion:
		if damage > m.armor[armor_loc]:
			damage -= m.armor[armor_loc]
			m.armor[armor_loc] = 0.0
			if damage >= m.internal[body]:
				damage -= m.internal[body]
				injure_body_location(rules, rng, m, body, m.internal[body], now)
				if damage > 0.0:
					_transfer(rules, rng, m, body, damage, master_id, now)
			else:
				injure_body_location(rules, rng, m, body, damage, now)
		else:
			m.armor[armor_loc] -= damage
		return

	if m.internal[body] > 0.0:
		if damage >= m.internal[body]:
			damage -= m.internal[body]
			injure_body_location(rules, rng, m, body, m.internal[body], now)
			if damage > 0.0:
				if ammo_explosion:
					_vent(m, body, damage)
				else:
					_transfer(rules, rng, m, body, damage, master_id, now)
		else:
			injure_body_location(rules, rng, m, body, damage, now)
	elif ammo_explosion:
		_vent(m, body, damage)
	else:
		_transfer(rules, rng, m, body, damage, master_id, now)


static func _transfer(rules: SimRules, rng: SimRng, m: SimMech, body: int, damage: float, master_id: int, now: float) -> void:
	if body == B.CTORSO or body == B.HEAD:
		return  # nowhere to go; the excess is lost
	handle_weapon_hit(rules, rng, m, damage, int(rules.transfer_table[body]), master_id, now)


## CASE venting of ammo-explosion overflow into rear armour.
static func _vent(m: SimMech, body: int, damage: float) -> void:
	var rear := A.RCTORSO
	match body:
		B.LTORSO, B.LARM, B.LLEG: rear = A.RLTORSO
		B.RTORSO, B.RARM, B.RLEG: rear = A.RRTORSO
	m.armor[rear] = max(0.0, m.armor[rear] - damage)


## injureBodyLocation: returns true if the location was destroyed.
static func injure_body_location(rules: SimRules, rng: SimRng, m: SimMech, body: int, damage: float, now: float) -> bool:
	if body == B.CTORSO and m.ct_first_injured_time < 0.0:
		m.ct_first_injured_time = now
	m.internal[body] = max(0.0, m.internal[body] - damage)
	if m.internal[body] > 0.0:
		m._update_damage_state(body)
		critical_hit(rules, rng, m, body, now)
		return false
	destroy_body_location(rules, rng, m, body, now)
	return true


## calcCriticalHit: 0-3 crits weighted by slot size; a top roll destroys a head or limb.
static func critical_hit(rules: SimRules, rng: SimRng, m: SimMech, body: int, now: float) -> void:
	if m.total_spaces[body] == 0:
		return
	var table := rules.critical_hit_table
	var roll := rng.roll(100)
	var count := 0
	if roll < table[0]:
		return
	elif roll < table[1]:
		count = 1
	elif roll < table[2]:
		count = 2
	elif body in [B.CTORSO, B.LTORSO, B.RTORSO]:
		count = 3
	if count == 0:
		destroy_body_location(rules, rng, m, body, now)
		return
	for i in count:
		var pick := rng.roll(m.total_spaces[body])
		var spaces: Array = m.crit_spaces[body]
		for slot in spaces.size():
			var inv: int = spaces[slot]
			var size := int(m.items[inv]["component"]["crits"]) if inv >= 0 else 0
			if pick < size:
				m.crit_hit[body][slot] = true
				hit_inventory_item(rules, rng, m, inv, now)
				break
			pick -= size


## hitInventoryItem: every component has 1 health, so a hit disables and destroys it.
static func hit_inventory_item(rules: SimRules, rng: SimRng, m: SimMech, inv: int, now: float) -> void:
	if inv < 0 or inv >= m.items.size():
		return
	var item := m.items[inv]
	item["health"] -= 1
	var loc: int = item["body_location"]
	var leg := loc == B.LLEG or loc == B.RLEG
	match item["form"]:
		"Actuator":
			if leg or not rules.fix_actuator_check:
				piloting_check(rng, m)
		"Gyroscope":
			piloting_check(rng, m)
	if item["health"] <= 0 and not item["disabled"]:
		item["disabled"] = true
		if item["form"] == "Engine":
			m.engine_blow_time = now + 5.0
			_disable(m)
	if item["health"] == 0:
		# The shipped game's destroyed-cockpit and destroyed-ammo cases do nothing but set
		# a damage effect (mech.cpp hitInventoryItem: COMPONENT_FORM_COCKPIT / _AMMO);
		# Mover::ammoExplosion exists but is never called. Only heat can blow ammo (H*).
		match item["form"]:
			"Actuator":
				if leg:
					piloting_check(rng, m, 100.0)


## Mover::ammoExplosion: remaining rounds x explosive damage (max 255) into the bin's location.
static func ammo_explosion(rules: SimRules, rng: SimRng, m: SimMech, inv: int, now: float) -> void:
	_injure_pilot(m, 2.0)
	var item := m.items[inv]
	var damage := minf(float(item["amount"]) * float(item["component"]["ammo"]["explosive_damage"]), 255.0)
	item["amount"] = 0
	handle_weapon_hit(rules, rng, m, damage, int(item["body_location"]), int(item["master_id"]), now)


## destroyBodyLocation (mech.cpp:6959).
static func destroy_body_location(rules: SimRules, rng: SimRng, m: SimMech, body: int, now: float) -> void:
	if m.damage_state[body] == SimMech.DamageState.DESTROYED:
		return
	m.internal[body] = 0.0
	m.damage_state[body] = SimMech.DamageState.DESTROYED
	m.armor[body] = 0.0
	if body == B.LLEG or body == B.RLEG:
		piloting_check(rng, m, 100.0)
	var spaces: Array = m.crit_spaces[body]
	for slot in spaces.size():
		if not m.crit_hit[body][slot] and spaces[slot] >= 0:
			m.crit_hit[body][slot] = true
			hit_inventory_item(rules, rng, m, spaces[slot], now)
	match body:
		B.CTORSO:
			if now <= m.ct_first_injured_time or (m.engine_blow_time > -1.0 and now <= m.engine_blow_time):
				_destroy_mech(rules, rng, m, now)
			else:
				_disable(m)
		B.RTORSO:
			destroy_body_location(rules, rng, m, B.RARM, now)
		B.LTORSO:
			destroy_body_location(rules, rng, m, B.LARM, now)


## BattleMech::pilotingCheck: d100 + modifiers >= Piloting means a fall.
static func piloting_check(rng: SimRng, m: SimMech, modifier: float = 0.0) -> void:
	if m.failed_piloting_check:
		return
	var roll := float(rng.roll(100)) + modifier
	if m.internal[B.RLEG] == 0.0 or m.internal[B.LLEG] == 0.0:
		roll += 100.0
	if m.gyro >= 0 and m.items[m.gyro]["health"] <= 0:
		roll += 100.0
	for hip in m.hip_actuators:
		if m.items[hip]["health"] <= 0:
			roll += 10.0
	if roll >= m.pilot.piloting:
		m.failed_piloting_check = true
		m.fallen = true


static func _injure_pilot(m: SimMech, wounds: float) -> void:
	if m.pilot.injure(wounds):
		_disable(m)


static func _disable(m: SimMech) -> void:
	if m.status != SimMech.Status.DESTROYED:
		m.status = SimMech.Status.DISABLED


static func _destroy_mech(rules: SimRules, rng: SimRng, m: SimMech, now: float) -> void:
	m.status = SimMech.Status.DESTROYED
