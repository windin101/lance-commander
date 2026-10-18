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

# Heat (combat-rules.md H1-H8).
var heat_enabled := true
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
