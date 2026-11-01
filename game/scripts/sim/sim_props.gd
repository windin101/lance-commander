class_name SimProps
extends RefCounted
## Destructible map props (LANCE-21 follow-up, Lee's decision): fences, barricades and sandbag lines are class-11 terrain objects with DmgLevel 0
## in the original, i.e. inert (terrobj.cpp:768-773: not tangible, already "destroyed"). Here they take damage from contact and impact only:
##   - a mech or ground vehicle moving over one crushes it (the original's crush for damageable terrain objects: terrobj.cpp:246-260),
##   - an explosion, strike or ground-targeted shot within reach hurts it by the damage dealt.
## They are NOT SimUnits: no pathing or passability change, no line of sight, no AI or bot targets, no objectives. Idle props cost nothing: there is no
## per-tick pass over them, only a hash lookup per moving mover and one query per blast. The view hears prop_hit (frac) and prop_destroyed events and
## drives ObjectsView.set_damage / destroy (damaged state at 50 %, destroyed at 100 %).

const GRID_M := 16.0
const CRUSH_MECH_M := 3.0
const CRUSH_VEHICLE_M := 1.8
## appearance -> [damage level, piece length m]; a piece runs from its placement along local -z (see ObjectsView: yaw PI - rotation)
const TYPES := {
	"wirefence": [8.0, 8.6], "wirefencediag": [8.0, 12.1], "razorwirefence": [12.0, 8.6], "razorwirefencediag": [12.0, 12.1],
	"woodenfence": [8.0, 8.6], "woodenfencediag": [8.0, 12.2], "shantyfence": [8.0, 8.5],
	"sandbagwall": [20.0, 8.4], "sandbagbunker": [40.0, 6.0], "tripodbarricade": [6.0, 8.4], "smallbarricade": [6.0, 5.0],
	"corrigatedmetalbarricade": [15.0, 8.4], "sawhorsebarricade": [3.0, 1.6],
}
## Pieces whose placement rotation is a quarter turn off the run they belong to (degrees added to the rotation). Measured over all 24 maps:
## the diagonal pieces lie across their line at the raw rotation and join end to end at +-90, and shantyfence's original runs along -x,
## not -z, while its v3 model is built along -z. ObjectsView turns the models by the same offset, so the sim footprint and the drawn piece agree.
const YAW_OFFSET := {"wirefencediag": -90.0, "razorwirefencediag": -90.0, "woodenfencediag": -90.0, "shantyfence": -90.0}

var world: SimWorld
var props: Array[Dictionary] = []  # {index, a, b, level, damage, done}
var _grid := {}  # Vector2i -> Array[int] (prop ids)


func _init(w: SimWorld) -> void:
	world = w


## Direction a piece runs on the sim plane for a placement rotation (degrees): ObjectsView turns the node by PI - rotation about Y and a
## piece spans local -z, which is (-sin r, -cos r) in sim coordinates (sim y is world -z).
static func direction(rotation_deg: float) -> Vector2:
	var r := deg_to_rad(rotation_deg)
	return Vector2(-sin(r), -cos(r))


func add(object_index: int, appearance: String, pos: Vector2, rotation_deg: float) -> void:
	var t: Array = TYPES[appearance]
	var a := pos
	var b := pos + direction(rotation_deg + float(YAW_OFFSET.get(appearance, 0.0))) * float(t[1])
	var id := props.size()
	props.append({"index": object_index, "a": a, "b": b, "level": float(t[0]), "damage": 0.0, "done": false})
	var lo := Vector2(minf(a.x, b.x), minf(a.y, b.y)) - Vector2.ONE * CRUSH_MECH_M
	var hi := Vector2(maxf(a.x, b.x), maxf(a.y, b.y)) + Vector2.ONE * CRUSH_MECH_M
	for cy in range(int(floor(lo.y / GRID_M)), int(floor(hi.y / GRID_M)) + 1):
		for cx in range(int(floor(lo.x / GRID_M)), int(floor(hi.x / GRID_M)) + 1):
			var key := Vector2i(cx, cy)
			if not _grid.has(key):
				_grid[key] = []
			(_grid[key] as Array).append(id)


static func _seg_dist(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var l2 := ab.length_squared()
	if l2 < 0.0001:
		return p.distance_to(a)
	return p.distance_to(a + ab * clampf((p - a).dot(ab) / l2, 0.0, 1.0))


## A moving mech or ground vehicle crushes the pieces under it (called once per tick for movers that moved).
func touch(m: SimUnit) -> void:
	if m.flying or m.is_disabled():
		return
	var reach := CRUSH_MECH_M if m is SimMech else CRUSH_VEHICLE_M
	var list: Array = _grid.get(Vector2i(int(floor(m.position.x / GRID_M)), int(floor(m.position.y / GRID_M))), [])
	for id in list:
		var p: Dictionary = props[id]
		if not p["done"] and _seg_dist(m.position, p["a"], p["b"]) <= reach:
			_hurt(id, INF, m.position, true)


## An explosion, strike or ground shot at `at` hurts every piece within `radius_m` by `damage`.
func blast(at: Vector2, radius_m: float, damage: float) -> void:
	if props.is_empty():
		return
	var seen := {}
	for cy in range(int(floor((at.y - radius_m) / GRID_M)), int(floor((at.y + radius_m) / GRID_M)) + 1):
		for cx in range(int(floor((at.x - radius_m) / GRID_M)), int(floor((at.x + radius_m) / GRID_M)) + 1):
			for id in _grid.get(Vector2i(cx, cy), []):
				if seen.has(id):
					continue
				seen[id] = true
				var p: Dictionary = props[id]
				if not p["done"] and _seg_dist(at, p["a"], p["b"]) <= radius_m:
					_hurt(id, damage, at, false)


func _hurt(id: int, amount: float, at: Vector2, crush: bool) -> void:
	var p: Dictionary = props[id]
	p["damage"] = minf(float(p["damage"]) + amount, float(p["level"]))
	var frac := float(p["damage"]) / float(p["level"])
	world.events.append({"type": "prop_hit", "index": p["index"], "frac": frac, "at": at, "crush": crush})
	if frac >= 1.0:
		p["done"] = true
		world.events.append({"type": "prop_destroyed", "index": p["index"], "at": at, "crush": crush})
