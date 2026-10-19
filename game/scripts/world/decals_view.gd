class_name DecalsView
extends Node3D
## Ground marks (world-rendering step 4, textures from tools/art/decals.py), as the original's crater manager
## drew them (MCLib/crater.cpp; mech3d.cpp:3207-3323 for footprints, weaponbolt.cpp for impact craters,
## gvehicl.cpp for vehicle deaths): each mech's own footprints at every footfall, alternating feet; craters
## where shots miss and strikes land; a scorch mark under every wreck; a spreading ring where a mech wades.
## Pools are capped (oldest marks recycled) and footprints fade out. Decals project only onto the terrain
## (render layer 2: TerrainView puts the ground on it), never onto units or buildings.

const TERRAIN_LAYER := 2
const MAX_FEET := 360
const MAX_CRATERS := 160
const FOOT_LIFE := 90.0

var map: SimMap
var _feet: Array[Decal] = []
var _feet_age: Array[float] = []
var _craters: Array[Decal] = []
var _left: Dictionary = {}  # unit index -> next foot is left
var _tex: Dictionary = {}
var _wakes: Array = []  # [MeshInstance3D, age]


func setup(sim_map: SimMap) -> void:
	map = sim_map


func _texture(path: String) -> Texture2D:
	if not _tex.has(path):
		_tex[path] = load(path) if ResourceLoader.exists(path) else null
	return _tex[path]


func _decal(tex: Texture2D, size: float) -> Decal:
	var d := Decal.new()
	d.texture_albedo = tex
	d.size = Vector3(size, 6.0, size)
	d.cull_mask = TERRAIN_LAYER
	d.upper_fade = 0.3
	d.lower_fade = 0.3
	d.distance_fade_enabled = true
	d.distance_fade_begin = 600.0
	d.distance_fade_length = 200.0
	add_child(d)
	return d


## A footfall of mech `unit` (appearance `model`) at its view's transform; `foot_m` is the print length.
func footstep(unit: int, model: String, xf: Transform3D, foot_m: float) -> void:
	var at := xf.origin
	if map and at.y < map.water_level_m + 0.3:
		_wake(Vector3(at.x, map.water_level_m + 0.05, at.z), foot_m * 1.6)
		return
	var left: bool = _left.get(unit, true)
	_left[unit] = not left
	var tex := _texture("res://assets/decals/feet/%s_%s.png" % [model.trim_suffix("_hd"), "l" if left else "r"])
	if tex == null:
		return
	var side := xf.basis.x.normalized() * foot_m * 0.42 * (-1.0 if left else 1.0)
	var d: Decal
	if _feet.size() < MAX_FEET:
		d = _decal(tex, foot_m)
		_feet.append(d)
		_feet_age.append(0.0)
	else:
		var i := _oldest_foot()
		d = _feet[i]
		d.texture_albedo = tex
		d.size = Vector3(foot_m, 6.0, foot_m)
		_feet_age[i] = 0.0
	var fwd := -xf.basis.z
	fwd.y = 0.0
	d.global_transform = Transform3D(Basis.looking_at(fwd.normalized() if fwd.length() > 0.01 else Vector3.FORWARD, Vector3.UP), at + side)
	d.modulate = Color(1, 1, 1, 0.9)


func _oldest_foot() -> int:
	var best := 0
	for i in _feet_age.size():
		if _feet_age[i] > _feet_age[best]:
			best = i
	return best


## A crater at ground point `p` (sim xy), `size_m` across. Big strikes and wreck sites also get a scorch.
func crater(p: Vector2, size_m: float, scorch := false) -> void:
	if map == null:
		return
	var h := map.height_at(p)
	if h < map.water_level_m:
		return
	var tex := _texture("res://assets/decals/%s.png" % ("scorch" if scorch else "crater_%d" % (randi() % 4)))
	var d: Decal
	if _craters.size() < MAX_CRATERS:
		d = _decal(tex, size_m)
		_craters.append(d)
	else:
		d = _craters.pop_front()
		d.texture_albedo = tex
		d.size = Vector3(size_m, 6.0, size_m)
		_craters.append(d)
	d.global_transform = Transform3D(Basis(Vector3.UP, randf() * TAU), TerrainView.to_3d(p, h))


func _wake(at: Vector3, size_m: float) -> void:
	var m := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(size_m, size_m)
	q.orientation = PlaneMesh.FACE_Y
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = _texture("res://assets/decals/wake.png")
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	q.material = mat
	m.mesh = q
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(m)
	m.global_position = at
	_wakes.append([m, 0.0])


func _process(delta: float) -> void:
	for i in _feet.size():
		_feet_age[i] += delta
		var a := clampf(1.0 - (_feet_age[i] - FOOT_LIFE * 0.6) / (FOOT_LIFE * 0.4), 0.0, 0.9)
		_feet[i].modulate.a = a
	for w in _wakes.duplicate():
		w[1] += delta
		var t: float = w[1] / 2.0
		var mi: MeshInstance3D = w[0]
		mi.scale = Vector3.ONE * (1.0 + 1.5 * t)
		(mi.mesh.material as StandardMaterial3D).albedo_color.a = clampf(1.0 - t, 0.0, 1.0)
		if t >= 1.0:
			mi.queue_free()
			_wakes.erase(w)
