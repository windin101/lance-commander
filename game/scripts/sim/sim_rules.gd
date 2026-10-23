class_name SimRules
extends RefCounted
## Rule tables and tunables for the combat simulation, built from the converted
## data (GameData or any object with components / gamesys / heat_table).
## See docs/specs/combat-rules.md for where each value comes from.

const NUM_ARMOR_LOCATIONS := 11
const NUM_HIT_ARCS := 4
const MAP_CELL_DIAGONAL := 128.0 / 3.0 * 1.4142 * 0.2  # metres (Move.cpp:803)

enum WeaponRange { SHORT, MEDIUM, LONG }
enum Section { TOP, MIDDLE, BOTTOM }
enum Arc { FRONT, REAR, LEFT, RIGHT }

var components: Dictionary = {}  # master id -> component
var weapon_ranges: Array = [[0.0, 60.0], [30.0, 120.0], [60.0, 180.0]]  # [min, long] metres
var head_shot_modifier := 0.08
var arm_shot_modifier := 0.15
var leg_shot_modifier := 0.20
var weapon_specialist_modifier := 20.0
var hit_location_table: Array = []  # 3 sections x 4 arcs x 11 armour locations
var critical_hit_table: Array = [58, 83, 97, 100]
var transfer_table: Array = [1, -1, 1, 1, 2, 3, 2, 3]
var player_skills: Array = [125, 100, 75, 50]
var enemy_skills: Array = [50, 100, 125, 150]
var difficulty := 1
var destruct_damage := 20.0

# Deliberate fixes of original bugs (combat-rules.md "Deliberate changes").
var fix_enemy_difficulty := true
var fix_range_specialists := true
var fix_actuator_check := true

# Sight (I90, I91): the original's contact and line-of-sight model. Off gives the old
# placeholders (contacts: any team mover within 500 m; weapons fire without LOS).
var original_contacts := true
var line_of_sight := true
var max_tree_los := 6  # gamesys General MaxTreeLOSBlock
## Indirect-fire weapons fire on a team mate's LOS (gamesys IndirectFireWeaponComponentIndex,
## warrior.cpp:3402-3410): LRM5, Swarm LRM5, LRM (130) and the Long Tom.
var indirect_fire_ids: Array = [120, 123, 130, 160]
## Area-effect weapons do their damage by an explosion at the target, hit or miss
## (weaponbolt.cpp:762-794): master id -> [AreaEffectDamage, AreaEffectRadius in metres] from the
## weapon's bolt FIT (longtom.fit 15 / 187 wu, swarmLRM.fit 3 / 120 wu). The ids are gamesys
## AreaEffectWeaponComponentIndex.
var area_effect_weapons := true
var area_effect := {160: [15.0, 187.0 * 0.2], 123: [3.0, 120.0 * 0.2]}
## Mines (gamesys [Mine]; mech.cpp:3731-3778, gvehicl.cpp:1355-1420, 3605-3637).
var mine := {"damage": 12.0, "splash_damage": 0.0, "splash_range": 15.0, "wait_time": 0.5, "min_tonnage": 35.0}
## Refit (gamesys Mover:General RefitRange / RefitTime / RefitAmount; support-powers.md 3.4, 3.7).
var refit := {"range": 30.0, "time": 1.0, "amount": 30.0, "power_down": 3.0}
var default_attack_radius := 275.0  # gamesys Warrior DefaultAttackRadius (warrior.cpp:290, 905)
## F6 / I12: an engaged AI unit fires only at its brain's target (combatDecisionTree,
## warrior.cpp:3493, 3532-3538). Off restores the port's old fire-at-will fallback.
var brain_target_only := true
## I92: brain moves walk unless the script asks to run (corebrain.abx:235-237); an attack
## approaches at the pilot's last move speed (warrior.cpp:5574, 5314). Off: every brain move runs.
var brain_walk := true
## Attackers walk to an attack goal (Mover::calcMoveGoal: a cell on the fire-range ring with a
## line of sight, spread from group mates) instead of stopping at the first point in reach.
var attack_goals := true
## I93: torsos and turrets turn at their yaw rate and weapons lock relative to them
## (BattleMech::updateTorso mech.cpp:4580-4623, GroundVehicle::updateTurret gvehicl.cpp:2130-2156,
## weaponLocked gvehicl.cpp:4283, mech.cpp:7342); vehicles change speed at MaxAccel
## (gvehicl.cpp:2970-2993). Off: instant twist and speed.
var slew := true
## Death from above on a jump landing (mech.cpp:819-925).
var dfa := true

# Original behaviour kept on purpose (combat-rules.md "Kept original rules").
## O1 (I88, Lee 2026-10-23: copy the original): a vehicle fires only from weapon nodes 2-3
## (Weapon_01/02) and always picks its least-used node, so a shape with Weapon_03/04 (Partisan,
## Legion) stops firing after two shots (gvehicl.cpp:4601-4618, Gvactor.cpp:578-660).
var vehicle_weapon_nodes := true
## O2 (I97): the single-player UnlimitedAmmo preference, TRUE by default (logmain.cpp:53,
## 404-406): every ammo pool is UNLIMITED_SHOTS (mover.cpp:5784-5788). SimWorld.add_unit copies
## it onto each unit.
var unlimited_ammo := true

# Heat (combat-rules.md H1-H8).
var heat_enabled := true
## H9 (I89, Lee 2026-10-23: soften heat): the share of heat.csv fire_mod taken off the to-hit.
var heat_fire_mod_factor := 0.5
var heat_table: Array = []  # 31 rows from heat.csv
var heat := {
	"dissipation_rate": 0.3,  # fraction of capacity shed per second (tuned 2026-10-18, combat-rules.md)
	"check_frequency": 1.0,
	"shutdown_level": 25,
	"restart_level": 15,
	"sink_efficiency": 1.0,
	"body_state_heat": [0.0, 0.0, 0.15, 0.3, 0.15, 0.1, 0.75, 0.0, 0.0],
}

# Weapon-specialist groups (mover.cpp:6290-6370): specialty -> master ids.
const WEAPON_SPECIALTIES := {
	"LaserSpecialist": [139, 140, 147, 156],
	"PulseLaserSpecialist": [142, 144, 153, 151],
	"ERLaserSpecialist": [141, 143, 150, 152],
	"LightACSpecialist": [100, 103, 110],
	"MediumACSpecialist": [101, 108, 111],
	"HeavyACSpecialist": [102, 109, 112],
	"LRMSpecialist": [120, 123],
	"SRMSpecialist": [124, 125],
	"PPCSpecialist": [145, 146, 154],
	"GaussSpecialist": [99],
	"SmallArmsSpecialist": [114, 155],
}


static func from_data(data: Object) -> SimRules:
	var r := SimRules.new()
	r.components = data.components
	var g: Dictionary = data.gamesys
	var wr: Dictionary = g["WeaponRanges"]
	r.weapon_ranges = [wr["Short"], wr["Medium"], wr["Long"]]
	var fire: Dictionary = g["Mover:FireWeapon"]
	r.head_shot_modifier = fire.get("HeadShotModifier", 0.08)
	r.arm_shot_modifier = fire.get("ArmShotModifier", 0.15)
	r.leg_shot_modifier = fire.get("LegShotModifier", 0.20)
	r.hit_location_table = _ints(g["Mech:FireWeapon"]["HitLocationTable"])
	r.critical_hit_table = _ints(g["Mech:Damage"]["CriticalHitTable"])
	r.transfer_table = _ints(g["Mech:Damage"]["MechTransferHitTable"])
	r.player_skills = _ints(g["DifficultySettings"]["PlayerSkills"])
	r.enemy_skills = _ints(g["DifficultySettings"]["EnemySkills"])
	var mh: Dictionary = g.get("Mech:Heat", {})
	r.heat["check_frequency"] = mh.get("HeatCheckFrequency", 1.0)
	r.heat["shutdown_level"] = int(mh.get("HeatShutdown", 25))
	r.heat["sink_efficiency"] = mh.get("HeatSinkEfficiency", 1.0)
	if mh.has("BodyStateHeat"):
		r.heat["body_state_heat"] = mh["BodyStateHeat"]
	r.heat_table = data.heat_table
	var gen: Dictionary = g.get("General", {})
	r.max_tree_los = int(gen.get("MaxTreeLOSBlock", 6))
	var mg: Dictionary = g.get("Mover:General", {})
	if mg.has("IndirectFireWeaponComponentIndex"):
		r.indirect_fire_ids = _ints(mg["IndirectFireWeaponComponentIndex"]).filter(func(v): return v >= 0)
	if mg.has("AreaEffectWeaponComponentIndex"):
		var ids := _ints(mg["AreaEffectWeaponComponentIndex"]).filter(func(v): return v >= 0)
		for k in r.area_effect.keys():
			if not (k in ids):
				r.area_effect.erase(k)
	r.refit["range"] = float(mg.get("RefitRange", 30.0))
	r.refit["time"] = float(mg.get("RefitTime", 1.0))
	r.refit["amount"] = float(mg.get("RefitAmount", 30.0))
	var mn: Dictionary = g.get("Mine", {})
	r.mine["damage"] = float(mn.get("BaseDamage", 12.0))
	r.mine["splash_damage"] = float(mn.get("SplashDamage", 0.0))
	r.mine["splash_range"] = float(mn.get("SplashRange", 15.0))
	r.mine["wait_time"] = float(mn.get("MineWaitTime", 0.5))
	r.default_attack_radius = float(g.get("Warrior", {}).get("DefaultAttackRadius", 275.0))
	return r


static func _ints(a: Array) -> Array:
	return a.map(func(v): return int(v))


func component(master_id: int) -> Dictionary:
	return components.get(master_id, {})


func range_index(range_name: String) -> int:
	match range_name:
		"short": return WeaponRange.SHORT
		"medium": return WeaponRange.MEDIUM
		"long": return WeaponRange.LONG
	return -1


func hit_location_weights(section: int, arc: int) -> Array:
	var start := section * (NUM_ARMOR_LOCATIONS * NUM_HIT_ARCS) + arc * NUM_ARMOR_LOCATIONS
	return hit_location_table.slice(start, start + NUM_ARMOR_LOCATIONS)


## Heat-table row for a level (0-30), or an all-zero row when heat is off.
func heat_row(level: int) -> Dictionary:
	if not heat_enabled or heat_table.is_empty():
		return {"shutdown_pct": 0, "ammo_explosion_pct": 0, "move_mod": 0, "fire_mod": 0, "injuries": 0}
	return heat_table[clampi(level, 0, heat_table.size() - 1)]
