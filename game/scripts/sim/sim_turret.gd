class_name SimTurret
extends SimStructure
## A map turret (Code/turret.cpp, object class 21): a building that turns its gun to the nearest
## enemy mover inside its attack radius and fires its 1-4 weapons with the type's own pilot skill.
## Linked to a control building (its parent): it takes the control's team, and goes dark for good
## when the control is destroyed, disabled or put to sleep (turret.cpp:640-664).
## Behaviour notes cite turret.cpp; docs/specs/combat-rules.md "Turrets" sums them up.

const MAX_WEAPONS := 4  # MAX_TURRET_WEAPONS
## turret.cpp:634, 673: the gun is "facing" its target within +/-10 degrees.
const FACING_DEG := 10.0
## The pop-up gesture (gestures 0 -> 1 -> 2, updateAnimations turret.cpp:444-520) must finish
## before a turret can fire. Its frames are not converted, so one opening time for all types.
const POP_UP_TIME := 1.0

var pilot_skill := 50.0
var attack_m := 0.0  # AttackRadius (it replaces the extent radius, turret.cpp:2142), metres
var yaw_rate := 20.0  # MaxTurretYawRate, degrees per second
var turret_yaw := 0.0  # the gun's heading, degrees (0 = north, clockwise)
var little_extent_m := 7.0  # LittleExtent: blasts must reach this close (carnage.cpp:400-420)
var active := true  # getAwake(): false once the control is lost, for good
var can_fire_time := INF  # when the pop-up has opened (INF: closed)
var gun_target: SimUnit = null  # targetWID
const SCAN_PERIOD := 0.5
var next_scan := 0.0


func kind() -> String:
	return "turret"


## turret.cpp:129-235 (TurretType::init) from objects.json; positions in metres.
static func from_type(t: Dictionary, rules: SimRules) -> SimTurret:
	var u := SimTurret.new()
	var td: Dictionary = t.get("turret", {})
	u.name = String(t.get("name", "Turret"))
	u.model = String(t.get("appearance", ""))
	u.damage_level = maxf(float(td.get("damage_level", 25)), 0.001)
	u.pilot_skill = float(td.get("pilot_skill", 50))
	u.attack_m = float(td.get("attack_radius", t.get("extent_radius", 0.0))) * 0.2
	u.yaw_rate = float(td.get("yaw_rate", 20.0))
	u.los_factor = float(td.get("los_factor", 1.0))
	u.little_extent_m = float(td.get("little_extent", 35.0)) * 0.2
	u.extent_m = u.little_extent_m
	u.explosion_damage = float(td.get("explosion_damage", 0.0))
	u.explosion_radius_m = float(td.get("explosion_radius", 0.0)) * 0.2
	u.tonnage = float(td.get("tonnage", 20))
	for mid in td.get("weapons", []):
		if int(mid) < 0:
			continue
		var comp := rules.component(int(mid))
		if comp.is_empty():
			continue
		u.items.append({"component": comp, "form": comp["form"], "master_id": int(mid), "health": 1,
			"disabled": false, "amount": 1, "ready_time": 0.0, "body_location": -1})
		u.num_weapons += 1
	return u


func sensor_works() -> bool:
	return false


## Turret::update (turret.cpp:525-934), once per sim tick.
func update(world: SimWorld, dt: float) -> void:
	if is_destroyed():
		gun_target = null
		return
	if parent != null and active:
		if parent.is_destroyed() or parent.is_disabled() or not parent.awake:
			active = false  # setAwake(false): the generator or control is gone (turret.cpp:617-633)
			awake = false
			gun_target = null
			can_fire_time = INF
			world.events.append({"type": "turret_down", "unit": id})
		elif parent.team != team:
			team = parent.team  # follows its control (turret.cpp:636-646)
			commander = parent.commander
			gun_target = null
			next_scan = 0.0
			world.events.append({"type": "turret_team", "unit": id, "team": team})
	if not active or team < 0:
		return
	# targetWID: dropped when disabled, friendly or out of the radius (turret.cpp:595-607); the
	# collision pass then takes the closest enemy mech or vehicle inside it (turret.cpp:238-316)
	if gun_target and (gun_target.is_disabled() or not gun_target.exists or gun_target.team == team \
			or gun_target.position.distance_to(position) > attack_m):
		gun_target = null
	# The original's collision pass offers the closest enemy every frame; the port looks every
	# SCAN_PERIOD, which is the cost of dozens of turrets per map.
	if world.time >= next_scan:
		next_scan = world.time + SCAN_PERIOD
		_acquire(world)
	if gun_target == null:
		can_fire_time = INF  # closing (gesture 3 -> 0)
		return
	_aim_and_fire(world, dt)


func _acquire(world: SimWorld) -> void:
	var best_d := gun_target.position.distance_to(position) if gun_target else INF
	for o in world.movers():
		if not o.exists or o.is_disabled() or o.team == team or o.team < 0:
			continue
		var d := o.position.distance_to(position)
		if d <= attack_m and d < best_d:
			best_d = d
			gun_target = o


func _aim_and_fire(world: SimWorld, dt: float) -> void:
	if can_fire_time == INF:
		can_fire_time = world.time + POP_UP_TIME
	var rel := wrapf(rad_to_deg(atan2(gun_target.position.x - position.x, gun_target.position.y - position.y)) - turret_yaw, -180.0, 180.0)
	if absf(rel) > FACING_DEG:
		turret_yaw = wrapf(turret_yaw + clampf(rel, -yaw_rate * dt, yaw_rate * dt), 0.0, 360.0)
		return  # not FACING_TARGET: no weapon is ready (isWeaponReady, turret.cpp:960-970)
	if world.time < can_fire_time:
		return
	for w in num_weapons:
		if float(items[w]["ready_time"]) <= world.time:
			world.turret_fire(self, w, gun_target)


## Turret::calcAttackChance (turret.cpp:993-1075): the type's pilot skill, +50 against a target
## standing still; no range-tolerance, no difficulty scaling and no upper clamp. -1 out of range.
func turret_attack_chance(rules: SimRules, w: int, t: SimUnit) -> float:
	var weapon: Dictionary = items[w]["component"].get("weapon", {})
	var span: Array = rules.weapon_ranges[rules.range_index(weapon.get("range", "short"))]
	var d := position.distance_to(t.position)
	if d <= float(span[0]) or d > float(span[1]):
		return -1.0
	var chance := pilot_skill
	if t.speed == 0.0:
		chance += 50.0
	if t is SimMech and t.pilot:
		var tp: SimPilot = t.pilot
		if t.tonnage < 40 and tp.has("LightMechSpecialist"):
			chance -= 30.0
		elif t.tonnage >= 40 and t.tonnage < 60 and tp.has("MediumMechSpecialist"):
			chance -= 20.0
		elif t.tonnage >= 60 and t.tonnage < 80 and tp.has("HevayMechSpecialist"):
			chance -= 10.0
		elif t.tonnage >= 80 and t.tonnage < 100 and tp.has("AssaultMechSpecialist"):
			chance -= 10.0
		chance = maxf(chance, 5.0)
	return chance
