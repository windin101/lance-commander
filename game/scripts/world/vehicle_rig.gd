class_name VehicleRig
extends RefCounted
## The moving parts of a ground vehicle's model, driven from the sim each frame (LANCE-17): the turret traverses to
## the sim's turret_rel, the gun elevates toward the target within the sidecar's limits, wheels spin by distance
## travelled over their radius (backwards when reversing), steering wheels turn into the curve, and track belts scroll,
## counter-rotating on a turn on the spot. Everything comes from the interpolated pose, so it needs no sim state.
##
## Node names (case-insensitive), as the art pipeline emits them:
##   turret            yaws about the model's up axis (the 2001 models' "*turret*" nodes count too)
##   gun               under the turret; pitches about the model's lateral axis (2001: TankGguns, LrmPods, ...)
##   wheel_*           spins about the lateral axis; radius = half its mesh's height
##   steer_*           a steering wheel's pivot: yaws by the steering angle (its wheel_* sits under it)
##   track_l, track_r  belt meshes: the v3 shader scrolls their UV strip (instance uniform track_strip)
## Sidecar res://assets/v3/vehicles/<name>.v3.json, all optional:
##   "gun_pitch": [min, max] degrees, up positive; absent = the gun doesn't elevate
##   "tracks": {"track_l": [v0, v_len, belt_m], ...}: the belt's UV strip (start, height) along the tread, v increasing
##     the way the belt runs when driving forward, and the belt's length in metres
## The HD (_hd) and v2 vehicles are one merged hd_body mesh, so only the 2001 models (--no-hd) and v3 parts move.

const LEGACY_GUNS := ["tankgguns", "mog_guns", "lrmpods", "tf_missilepods", "srm_pack", "h_biggun"]
const MAX_STEER := 35.0  # degrees
const STEER_SMOOTH := 8.0  # 1/s: steering follows the curve, not the frame-to-frame jitter

var turret: Node3D
var gun: Node3D
var wheels: Array[Node3D] = []
var steers: Array[Node3D] = []
var tracks: Array[MeshInstance3D] = []
var turret_yaw := 0.0  # shown, degrees (+ = clockwise), follows the sim's turret_rel at the turret rate
var gun_pitch := 0.0  # shown, degrees (+ = up)
var steer := 0.0  # degrees (+ = right)
var wheel_turn := 0.0  # radians rolled by a 1 m wheel (each wheel divides by its own radius)
var belt := Vector2.ZERO  # left, right belt travel in metres

var _rest := {}  # node -> rest Basis
var _axis := {}  # node -> [up, lateral] in its parent's frame
var _radius := {}  # wheel -> metres
var _strip := {}  # track mesh -> [v0, v_len, belt_m]
var _pitch_limits := Vector2.ZERO
var _gun_height := 2.0
var _half_track := 1.2
var _wheelbase := 3.0
var _last := Vector2.INF
var _last_facing := 0.0


## The rig for a model, or null when nothing on it can move.
static func build(model: Node3D, sidecar: Dictionary) -> VehicleRig:
	var r := VehicleRig.new()
	for n in model.find_children("*", "Node3D", true, false):
		var low := String(n.name).to_lower()
		if r.turret == null and (low == "turret" or low.contains("turret")):
			r.turret = n
		elif low.begins_with("steer_"):
			r.steers.append(n)
		elif low.begins_with("wheel_"):
			r.wheels.append(n)
		elif (low == "track_l" or low == "track_r") and n is MeshInstance3D:
			r.tracks.append(n)
	if r.turret:
		for n in r.turret.find_children("*", "Node3D", true, false):
			var low := String(n.name).to_lower()
			if low == "gun" or low in LEGACY_GUNS:
				r.gun = n
				break
	# A part moves only if it carries a mesh: the HD models' turret nodes are empty markers over one merged hd_body,
	# and turning one would swing its weapon nodes (the muzzle flashes) away from the barrel on screen
	if r.turret and not _has_mesh(r.turret):
		r.turret = null
		r.gun = null
	if r.gun and not _has_mesh(r.gun):
		r.gun = null
	r.wheels.assign(r.wheels.filter(_has_mesh))
	if r.turret == null and r.wheels.is_empty() and r.tracks.is_empty():
		return null
	for n: Node3D in [r.turret, r.gun] + r.wheels + r.steers:
		if n:
			r._rest[n] = n.basis
			var b := _basis_above(n, model).inverse()
			r._axis[n] = [(b * Vector3.UP).normalized(), (b * Vector3.RIGHT).normalized()]
	for w in r.wheels:
		r._radius[w] = _wheel_radius(w)
	if not r.steers.is_empty():
		var front := 0.0
		for s in r.steers:
			front += _model_origin(s, model).z / r.steers.size()
		var rear: Array[float] = []
		for w in r.wheels:
			if not r.steers.any(func(s): return s.is_ancestor_of(w)):
				rear.append(_model_origin(w, model).z)
		if not rear.is_empty():
			r._wheelbase = maxf(absf(front - rear.reduce(func(a, b): return a + b) / rear.size()), 0.5)
	var strips: Dictionary = sidecar.get("tracks", {})
	for t in r.tracks:
		var s: Array = strips.get(String(t.name).to_lower(), [])
		if s.size() == 3 and float(s[1]) > 0.0 and float(s[2]) > 0.0:
			r._strip[t] = s
	if r.tracks.size() == 2:
		r._half_track = maxf(absf(_model_origin(r.tracks[0], model).x - _model_origin(r.tracks[1], model).x) / 2.0, 0.3)
	var gp: Array = sidecar.get("gun_pitch", [])
	if gp.size() == 2:
		r._pitch_limits = Vector2(float(gp[0]), float(gp[1]))
	if r.gun:
		r._gun_height = _model_origin(r.gun, model).y
	return r


## Metres travelled along the facing (degrees, 0 = north, clockwise) between two sim positions; negative = reversing.
static func travel(prev: Vector2, pos: Vector2, facing: float) -> float:
	return (pos - prev).dot(Vector2(sin(deg_to_rad(facing)), cos(deg_to_rad(facing))))


## Left and right belt travel for a move of `along` metres while yawing `dyaw` degrees (+ = clockwise), tracks
## half_track metres either side of the centre: on the spot they run in opposite directions.
static func belts(along: float, dyaw: float, half_track: float) -> Vector2:
	var arc := deg_to_rad(dyaw) * half_track
	return Vector2(along + arc, along - arc)


## The steering angle (degrees, + = right) for yawing dyaw degrees over `along` metres with this wheelbase.
## Too little travel to tell the curve: keep `last`.
static func steer_for(along: float, dyaw: float, wheelbase: float, last: float) -> float:
	if absf(along) < 0.005:
		return last
	return clampf(rad_to_deg(atan(wheelbase * deg_to_rad(dyaw) / along)), -MAX_STEER, MAX_STEER)


## Move the shown turret angle toward the sim's at up to `rate` degrees per second, the short way round.
static func turret_step(shown: float, want: float, rate: float, dt: float) -> float:
	var off := wrapf(want - shown, -180.0, 180.0)
	return wrapf(shown + clampf(off, -rate * dt, rate * dt), -180.0, 180.0)


## Pose the parts for the unit at pos (sim metres) facing `facing` degrees, dt seconds after the last frame.
## aim: the target's height above our ground and its distance, or Vector2.ZERO for none.
func update(pos: Vector2, facing: float, turret_rel: float, turret_rate: float, aim: Vector2, dt: float) -> void:
	if _last == Vector2.INF or _last.distance_to(pos) > 50.0:  # first frame, or placed by a script
		_last = pos
		_last_facing = facing
	var along := travel(_last, pos, facing)
	var dyaw := wrapf(facing - _last_facing, -180.0, 180.0)
	_last = pos
	_last_facing = facing
	wheel_turn = wrapf(wheel_turn + along, -1000.0, 1000.0)
	belt += belts(along, dyaw, _half_track)
	steer = lerpf(steer, steer_for(along, dyaw, _wheelbase, steer), clampf(STEER_SMOOTH * dt, 0.0, 1.0))
	turret_yaw = turret_step(turret_yaw, turret_rel, maxf(turret_rate, 30.0), dt) if dt > 0.0 else turret_rel
	if _pitch_limits != Vector2.ZERO and aim != Vector2.ZERO:
		var want := clampf(rad_to_deg(atan2(aim.x - _gun_height, aim.y)), _pitch_limits.x, _pitch_limits.y)
		gun_pitch = move_toward(gun_pitch, want, 30.0 * dt)
	elif dt > 0.0:
		gun_pitch = move_toward(gun_pitch, 0.0, 30.0 * dt)
	_pose()


func _pose() -> void:
	if turret:
		_turn(turret, 0, -deg_to_rad(turret_yaw))
	if gun:
		_turn(gun, 1, -deg_to_rad(gun_pitch))  # +X: up is -angle (Y -> Z is +)
	for w in wheels:
		_turn(w, 1, wrapf(wheel_turn / float(_radius[w]), -TAU, TAU))  # +X: the top rolls forward (+Z)
	for s in steers:
		_turn(s, 0, -deg_to_rad(steer))
	for t in tracks:
		var s: Array = _strip.get(t, [])
		if not s.is_empty():
			var left := String(t.name).to_lower() == "track_l"
			var scroll := fposmod((belt.x if left else belt.y) / float(s[2]), 1.0)
			t.set_instance_shader_parameter("track_strip", Vector3(float(s[0]), float(s[1]), scroll))


func _turn(n: Node3D, which: int, angle: float) -> void:
	n.basis = Basis(_axis[n][which], angle) * (_rest[n] as Basis)


## The basis from the model's frame down to n's parent (the frame n's own basis lives in).
static func _basis_above(n: Node3D, model: Node3D) -> Basis:
	var b := Basis.IDENTITY
	var p := n.get_parent()
	while p is Node3D and p != model.get_parent():
		b = (p as Node3D).basis * b
		if p == model:
			break
		p = p.get_parent()
	return b


static func _has_mesh(n: Node3D) -> bool:
	return n is MeshInstance3D or not n.find_children("*", "MeshInstance3D", true, false).is_empty()


static func _model_origin(n: Node3D, model: Node3D) -> Vector3:
	var t := Transform3D.IDENTITY
	var p: Node = n
	while p is Node3D and p != model:
		t = (p as Node3D).transform * t
		p = p.get_parent()
	return t.origin


static func _wheel_radius(w: Node3D) -> float:
	var box := AABB()
	var first := true
	for mi in ([w] if w is MeshInstance3D else []) + w.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if m.mesh == null:
			continue
		var bb: AABB = m.get_aabb() if m == w else m.transform * m.get_aabb()
		box = bb if first else box.merge(bb)
		first = false
	return maxf(box.size.y / 2.0, 0.05) if not first else 0.4
