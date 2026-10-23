extends Node
## Dev weapons range (I87): a real mission scene with the sim frozen, a shooter and a target mech 150 m apart
## on open ground, and a scripted programme per weapon family, fired through the game's own EffectsView.
##
##   godot --path game res://scenes/fx_range.tscn -- --family=laser [--mission=mc2_01] [--dist=150]
##         [--cam=yaw,pitch,distance] [--write-movie handled by Godot itself]
##
## Families: laser, ppc, autocannon, gauss, mg, missile, flamer, artillery, misses, water, damage, death, vehicle,
## building, all (and idle, probe for debugging).
## The programme quits when done, so `--write-movie out.avi --fixed-fps 30` records exactly one clip.

const PROGRAMS := {
	"laser": [[12, true], [15, true], [14, true], [17, true], [13, true], [16, true], [29, true], [30, true], [12, false], [17, false]],
	"ppc": [[4, true], [5, true], [4, true], [5, false], [4, false]],
	"autocannon": [[7, true, 103], [18, true], [18, true, 108], [19, true], [19, true, 112], [18, false], [19, false]],
	"gauss": [[10, true], [28, true], [10, true], [10, false], [28, false]],
	"mg": [[11, true], [11, true], [11, true], [11, false], [11, false]],
	"missile": [[9, true], [8, true], [8, true, 125], [74, true], [27, true], [9, false], [8, false]],
	"flamer": [[3, true], [3, true], [3, false]],
	"artillery": [[31, true], [31, false]],
	"misses": [[12, false], [18, false], [10, false], [9, false], [4, false], [11, false]],
}
const SPEED := {"EnergyWeapon": 0.0, "BallisticWeapon": 450.0, "MissileWeapon": 160.0}
const FORM := {"laser": "EnergyWeapon", "ppc": "EnergyWeapon", "flamer": "EnergyWeapon", "autocannon": "BallisticWeapon",
	"gauss": "BallisticWeapon", "mg": "BallisticWeapon", "artillery": "BallisticWeapon", "missile": "MissileWeapon"}

var view: Node3D  # the mission view
var shooter: SimUnit
var target: SimUnit
var _steps: Array = []  # [time, Callable]
var _t := 0.0
var _end := 0.0
var _args := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	view = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	_stage()
	var fam := String(_args.get("family", "laser"))
	var fams: Array = PROGRAMS.keys() + ["water", "damage", "death", "vehicle", "building"] if fam == "all" else [fam]
	var t := 1.0
	for f in fams:
		t = _program(f, t)
	_end = t + 1.0


func _stage() -> void:
	var w: SimWorld = view.world
	for u in w.units:
		if shooter == null and u is SimMech and u.team == view.sm.player_team:
			shooter = u
	for u in w.units:
		if target == null and u is SimMech and u.team != view.sm.player_team:
			target = u
	if target == null:  # no enemy mech: borrow a second player mech
		for u in w.units:
			if u is SimMech and u != shooter:
				target = u
				break
	var dist := float(_args.get("dist", "150"))
	# a site with a clear line of fire: the straight line 6 m up between them stays above the ground
	var c: Vector2 = shooter.position
	var best := INF
	for ring_m in [0.0, 150.0, 300.0, 450.0, 600.0]:
		for k in 12:
			var a := w.map.nearest_walkable(c + Vector2(ring_m, 0).rotated(k * TAU / 12.0))
			var b := w.map.nearest_walkable(a + Vector2(dist, 0))
			var ha := w.map.height_at(a) + 6.0
			var hb := w.map.height_at(b) + 6.0
			var worst := 0.0
			for i in range(1, 20):
				var f := i / 20.0
				worst = maxf(worst, w.map.height_at(a.lerp(b, f)) - lerpf(ha, hb, f) + 2.0)
			worst += absf(ha - hb) * 0.2
			if worst < best:
				best = worst
				shooter.position = a
				target.position = b
		if best <= 0.0:
			break
	shooter.facing = 90.0
	target.facing = 270.0
	for u in [shooter, target]:
		u.prev_position = u.position
		u.prev_facing = u.facing
		u.speed = 0.0
	# everything else out of the way
	for u in w.units:
		if u != shooter and u != target and u.is_mover() and view.views.has(u.id):
			view.views[u.id].visible = false
	var mid: Vector2 = (shooter.position + target.position) / 2.0
	var cam: RtsCamera = view.camera
	cam.limits = false
	cam.input_blocked = func() -> bool: return true  # no edge scroll from wherever the pointer sits
	cam.focus = Vector3(mid.x, 0, -mid.y)
	cam.yaw_deg = 0.0
	cam.pitch_deg = RtsCamera.DEFAULT_PITCH
	cam.distance = RtsCamera.DEFAULT_DISTANCE
	if _args.has("cam"):
		var v: PackedStringArray = String(_args["cam"]).split(",")
		cam.yaw_deg = float(v[0])
		if v.size() > 1: cam.pitch_deg = float(v[1])
		if v.size() > 2: cam.distance = float(v[2])
	for v in view.views.values():
		v.sync(1.0)
	if view.compass:
		view.compass.enabled = false
	if _args.has("focus-target"):
		cam.focus = Vector3(target.position.x, 0, -target.position.y)
	if _args.has("debug"):
		for u in [shooter, target]:
			var mv: MechView = view.views[u.id]
			var sk := mv.model.find_child("*", true, false)
			var bones := AABB()
			for s in mv.model.find_children("*", "Skeleton3D", true, false):
				var k := s as Skeleton3D
				for b in k.get_bone_count():
					var p := mv.to_local(k.to_global(k.get_bone_global_pose(b).origin))
					bones = bones.expand(p) if bones.size != Vector3.ZERO else AABB(p, Vector3.ZERO)
			print("BOUNDS ", u.model, " mesh=", mv.bounds, " bones=", bones, " weapon0=", mv.to_local(mv.muzzle_point(u.weapon_indices()[0])))


func _at(t: float, f: Callable) -> void:
	_steps.append([t, f])


## Queue one family's programme from time t; returns when it ends.
func _program(fam: String, t: float) -> float:
	match fam:
		"damage":
			_at(t, _set_damage.bind(0.45))
			_at(t + 3.0, _set_damage.bind(0.75))
			return t + 7.0
		"idle":  # nothing fired: a reference for artefacts that are not the effects'
			return t + 8.0
		"probe":  # one still particle of each kind in a row above the target, for debugging the pools
			_at(t, _probe)
			return t + 3.0
		"death":
			_at(t, _set_damage.bind(0.8))
			_at(t + 1.5, _kill)
			return t + 12.0
		"water":  # misses into the nearest open water: splashes and steam
			var wp := _water_point()
			if wp == Vector3.INF:
				return t
			_at(t, func() -> void: view.camera.focus = Vector3(wp.x, 0, wp.z))
			var k := t + 0.8
			for fx_id in [18, 19, 10, 9, 12, 4, 11, 31]:
				_at(k, _shoot_at.bind(fx_id, wp))
				k += 1.6
			return k + 1.5
		"vehicle":
			_at(t, _kill_vehicle)
			return t + 9.0
		"building":
			_at(t, _kill_building)
			return t + 10.0
	for shot in PROGRAMS.get(fam, []):
		var fx_id: int = shot[0]
		var comp: int = shot[2] if shot.size() > 2 else -1
		_at(t, _shoot.bind(fx_id, shot[1], comp))
		var s: Dictionary = view.effects.spec(fx_id, comp)
		var gap := 1.4
		match String(s.get("kind", "")):
			"missile", "shell":
				gap = 2.2
			"flame":
				gap = 1.8
		t += gap
	return t + 1.5


func _form_of(fx_id: int) -> String:
	var fam := String(view.effects.spec(fx_id).get("family", "laser"))
	return FORM.get(fam if fam in FORM else ("laser" if fam.contains("laser") else "autocannon"), "EnergyWeapon")


func _shoot(fx_id: int, hit: bool, comp: int) -> void:
	var sv: MechView = view.views[shooter.id]
	var tv: MechView = view.views[target.id]
	var form := _form_of(fx_id)
	var w := -1
	for i in shooter.weapon_indices():
		if String(shooter.items[i]["form"]) == form:
			w = i
			break
	if w < 0:
		w = shooter.weapon_indices()[0] if shooter.num_weapons > 0 else 0
	var from: Vector3 = sv.muzzle_point(w)
	var to: Vector3 = tv.body_point(randi_range(1, 7)) if hit else tv.aim_point()
	var speed: float = SPEED.get(form, 0.0)
	var flight := shooter.distance_to(target.position) / speed if speed > 0.0 else 0.0
	var opts := {"component": comp, "to_node": tv}
	var node := sv.muzzle_node(w)
	if node:
		opts["from_node"] = node
	opts["on_ground"] = func(at: Vector3, size_m: float, scorch: bool) -> void:
		view.decals.crater(Vector2(at.x, -at.z), size_m, scorch)
	view.effects.fire(fx_id, from, to, hit, flight, opts)


func _probe() -> void:
	var tv: MechView = view.views[target.id]
	var base := tv.global_position + Vector3(-30, 8, 0)
	var i := 0
	for k in ["flash", "spark", "fire", "flame", "smoke", "dust", "splash", "debris"]:
		var p := base + Vector3(i * 7.0, 0, 0)
		var v := Vector3(0, 0.01, 0) if k != "spark" else Vector3(0, 5, 0)
		view.effects.emit(k, p, v, Color(2, 2, 2, 1) if k in ["flash", "spark"] else Color(1, 1, 1, 1), 5.0, 2.8)
		i += 1


## Nearest point of deep water within 400 m of the target (Vector3.INF: none).
func _water_point() -> Vector3:
	var map: SimMap = view.world.map
	for r in range(40, 400, 20):
		for k in 24:
			var p: Vector2 = target.position + Vector2(r, 0).rotated(k * TAU / 24.0)
			if map.height_at(p) < map.water_level_m - 1.0 and map.height_at(p + Vector2(15, 0)) < map.water_level_m - 1.0:
				return TerrainView.to_3d(p, map.water_level_m)
	return Vector3.INF


func _shoot_at(fx_id: int, at: Vector3) -> void:
	var sv: MechView = view.views[shooter.id]
	var form := _form_of(fx_id)
	var speed: float = SPEED.get(form, 0.0)
	var from: Vector3 = sv.muzzle_point(shooter.weapon_indices()[0])
	view.effects.fire(fx_id, from, at + Vector3(0, 4, 0), false, from.distance_to(at) / speed if speed > 0.0 else 0.0)


func _set_damage(frac: float) -> void:
	for i in target.armor.size():
		target.armor[i] = target.max_armor[i] * (1.0 - frac)
	if target is SimMech:
		for i in target.internal.size():
			target.internal[i] = target.max_internal[i] * (1.0 - frac * 0.6)
		if frac > 0.7:
			target.damage_state[SimMech.Body.LARM] = SimMech.DamageState.DESTROYED


func _kill() -> void:
	target.status = SimUnit.Status.DESTROYED
	var tv: MechView = view.views[target.id]
	tv.sync(1.0)
	view.decals.crater(target.position, 10.0, true)
	view.effects.destroyed("mech", tv.global_position, tv.fx_scale(), tv.bounds.size.y)


## The nearest vehicle is parked beside the target and blown up.
func _kill_vehicle() -> void:
	var w: SimWorld = view.world
	for u in w.units:
		if u is SimVehicle and view.views.has(u.id) and u.tonnage >= 5.0:
			u.position = w.map.nearest_walkable(target.position + Vector2(-25, 18))
			u.prev_position = u.position
			var vv: MechView = view.views[u.id]
			vv.visible = true
			vv.sync(1.0)
			u.status = SimUnit.Status.DESTROYED
			vv.sync(1.0)
			view.decals.crater(u.position, 10.0, true)
			view.effects.destroyed("vehicle", vv.global_position, vv.fx_scale(), vv.bounds.size.y)
			return


## The building nearest the target goes up, framed by the camera.
func _kill_building() -> void:
	var w: SimWorld = view.world
	var best: SimUnit = null
	for u in w.units:
		if u is SimStructure and not u.is_disabled() and view.objects_view.nodes.has(u.object_index):
			var box: AABB = view.objects_view.bounds(u.object_index)
			if box.size.y < 4.0:
				continue
			if best == null or u.distance_to(target.position) < best.distance_to(target.position):
				best = u
	if best == null:
		return
	view.camera.focus = Vector3(best.position.x, 0, -best.position.y)
	_at(_t + 0.6, func() -> void:
		var box: AABB = view.objects_view.bounds(best.object_index)
		view.objects_view.destroy(best.object_index)
		view.decals.crater(best.position, 18.0, true)
		var base := Vector3(box.get_center().x, box.position.y, box.get_center().z)
		view.effects.destroyed("building", base, clampf(maxf(box.size.x, box.size.z) / 14.0, 0.6, 3.0), box.size.y))


func _process(delta: float) -> void:
	if _end <= 0.0:
		return
	_t += delta
	var keep: Array = []
	for s in _steps:
		if _t >= s[0]:
			(s[1] as Callable).call()
		else:
			keep.append(s)
	_steps = keep
	if _t >= _end and not _args.has("stay"):
		get_tree().quit()
