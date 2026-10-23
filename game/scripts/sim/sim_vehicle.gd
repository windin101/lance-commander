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
## Weapon nodes (Weapon_01..04) the appearance's shape has, -1 when unknown (not converted).
## GVAppearance numbers them after the 2 smoke nodes (Gvactor.cpp:291-321) and drops the ones the
## shape lacks at the first update (getLowestWeaponNode -> getWeaponNodePosition marks them -2,
## Gvactor.cpp:466-474, mover.cpp:3454-3466).
var mine_stock := 0  # MineLayer: mines left to lay (gvehicl.cpp:344, 4445); 0 = not a minelayer
var mine_sweeper := false
var laying_mines := false  # MOVE_MODE_MINELAYING (support-powers.md 3.5)
var mine_cell := Vector2i(-1, -1)  # cellRowToMine / cellColToMine: the last cell mined
var mine_dwell := 0.0  # timeInCurrent
var weapon_nodes := -1
var node_used: Array[int] = []  # nodeUsed per node
var node_ready: Array[float] = []  # when nodeRecycle reaches 0 again
const NODE_RECYCLE := 0.25  # BASE_NODE_RECYCLE_TIME (Gvactor.cpp:424)
const SMOKE_NODES := 2  # MAX_SMOKE_NODES (Gvactor.cpp:90)


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
	u.turret_rate = float(v.get("max_turret_yaw_rate", 0))
	u.max_accel = float(v.get("max_accel", 0.0))
	u.fire_arc_half = FIRE_ARC_HALF
	u.turn_rate = turn_rate_for(u.tonnage)
	u.explosion_damage = float(v.get("explosion_damage", 0))
	u.explosion_radius_m = float(v.get("explosion_radius", 0)) * 0.2
	u.refit_pool = float(v.get("refit_points", 0.0))
	u.resource_points = int(v.get("resource_points", 0))
	u.set_weapon_nodes(int(v.get("weapon_nodes", -1)))
	u.los_factor = float(v.get("los_factor", 1.0))
	u.mine_stock = int(v.get("mine_layer", 0))
	u.mine_sweeper = bool(v.get("mine_sweeper", false))
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


func set_weapon_nodes(n: int) -> void:
	weapon_nodes = n
	node_used.clear()
	node_ready.clear()
	for i in maxi(n, 0):
		node_used.append(0)
		node_ready.append(0.0)


## GVAppearance::getWeaponNode: the least-used existing node (the first on a tie), numbered as
## the original does (smoke nodes first, so 2-5), or -1 with none. Every vehicle node is
## MECH3D_WEAPONTYPE_ANY (Gvactor.cpp:320), so the weapon's form doesn't matter.
func pick_weapon_node() -> int:
	var best := -1
	var least := 999999999
	for i in node_used.size():
		if node_used[i] < least:
			least = node_used[i]
			best = i + SMOKE_NODES
	return best


## The single-player gate in GroundVehicle::fireWeapon (gvehicl.cpp:4601-4618): no node, a node
## above 3 or a node still recycling means no shot (return 3), with no recycle or ammo spent, so
## the weapon tries again (and picks the same node) next time.
func weapon_node_allows(node: int, now: float) -> bool:
	if node < 0 or node > 3:
		return false
	return node_ready[node - SMOKE_NODES] <= now + 0.0001


## setWeaponNodeUsed (Gvactor.cpp:427-435).
func use_weapon_node(node: int, now: float) -> void:
	var i := node - SMOKE_NODES
	if i >= 0 and i < node_used.size():
		node_used[i] += 1
		node_ready[i] = now + NODE_RECYCLE


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
