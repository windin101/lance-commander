class_name SimUnit
extends RefCounted
## Common state for anything that can be targeted: mechs, ground vehicles and
## structures. Holds identity, position, inventory, weapons, status, heat and
## the movement/order fields SimWorld drives. Damage models live in subclasses
## (SimMech, SimVehicle, SimStructure) and in SimCombat / SimVehicleCombat.

enum Status { NORMAL, SHUTDOWN, DISABLED, DESTROYED }
# Body states index gamesys BodyStateHeat (mech.cpp NUM_MECH_STATES order).
enum BodyState { PARKED, STANDING, WALKING, RUNNING, REVERSE, LIMPING, JUMPING, FALLEN_FORWARD, FALLEN_BACKWARD }

const OTHER_FORMS := ["JumpJet", "Cockpit", "Sensors", "LifeSupport", "Gyroscope", "PowerAmplifier",
	"ECM", "Probe", "Jammer", "Case", "Actuator", "Engine", "HeatSink"]
const WEAPON_FORMS := ["Weapon", "EnergyWeapon", "BallisticWeapon", "MissileWeapon"]

var id := -1
var name := ""
var model := ""  # appearance name, e.g. "bushwacker"
var paint: Array = []  # mission ARGB ints: highlight1, highlight2, base
var tonnage := 0.0
var team := 0
var is_player := false
var pilot: SimPilot
var part_index := -1  # mission Part number
var commander := -1
var group_index := -1  # position in its CommanderNGroup:M mates list
var group := -1  # M of its CommanderNGroup:M block
var part_id := 0  # ABL object ID: 512 + commander*192 + group*12 + mate; buildings 4096 + row*720 + col
var squad := 0  # FIT SquadNum: ABL unit IDs 1-511 match it
var warrior_index := 0  # FIT Pilot = [Warrior<n>]
var exists := true  # FIT Exists: a non-existent object is invisible to the sim and to ABL
var awake := true  # FIT Active
var ejected := false  # the pilot left (coreEject): the unit is inert

var position := Vector2.ZERO  # metres; x east, y north
var facing := 0.0  # degrees, 0 = north, clockwise positive
var body_state: int = BodyState.STANDING

var armor: Array[float] = []  # current, per armour location
var max_armor: Array[float] = []

## Inventory items: {component, form, master_id, health, disabled, amount, ready_time, body_location}
var items: Array[Dictionary] = []
var num_other := 0
var num_weapons := 0
var num_ammo := 0

var status: int = Status.NORMAL
var ignore_heat_discipline := false  # player "alpha strike": fire even past the heat limit
var powered_down := false  # ordered shutdown (corePower false): heat never restarts it
var heat := 0.0
var heat_capacity := 30.0
var heat_check_time := 0.0
var uses_heat := true

# Movement and orders (SimWorld).
var run_speed := 20.0  # m/s
var walk_speed := 10.0  # m/s
var max_torso_yaw := 120.0  # turret or torso twist
var fire_arc_half := 12.5  # gamesys Mover:FireWeapon FireArc / 2 (mover.cpp:1876)
var turn_rate := 180.0  # degrees per second
var hover := false  # hovercraft: may cross water
var speed := 0.0
var prev_position := Vector2.ZERO
var prev_facing := 0.0
var order: int = 0
var order_target: SimUnit = null
var current_target: SimUnit = null
var path := PackedVector2Array()
var path_index := 0
var repath_time := 0.0
var reported_disabled := false
var brain: RefCounted = null  # SimAbl.Pilot: the unit's original ABL brain
var brain_name := ""  # the mission Warrior's Brain script name
var last_attacker: SimUnit = null
var last_attacked_time := -1.0
var engage_m := 0.0  # auto-target radius limit (0 = weapon range); PBrain uses 100 m


func kind() -> String:
	return "unit"


func is_mover() -> bool:
	return true


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
