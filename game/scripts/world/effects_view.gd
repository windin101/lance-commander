class_name EffectsView
extends Node3D
## Short-lived weapon effects driven by SimWorld events: energy beams, tracer
## and missile projectiles over their flight time, impact flashes, explosions.

const BEAM_TIME := 0.15
const COLORS := {
	"EnergyWeapon": Color(0.4, 0.9, 1.0),
	"BallisticWeapon": Color(1.0, 0.85, 0.4),
	"MissileWeapon": Color(1.0, 0.55, 0.2),
	"Weapon": Color(1.0, 0.85, 0.4),
}

var _live: Array[Dictionary] = []  # {node, kind, t, life, from, to}
var _rng := RandomNumberGenerator.new()


func spawn_shot(from: Vector3, to: Vector3, form: String, hit: bool, flight: float) -> void:
	if not hit:
		to += Vector3(_rng.randf_range(-7, 7), _rng.randf_range(-2, 3), _rng.randf_range(-7, 7))
	var color: Color = COLORS.get(form, Color.WHITE)
	if form == "EnergyWeapon" or flight <= 0.0:
		var beam := _beam(from, to, color, 0.25)
		_live.append({"node": beam, "kind": "fade", "t": 0.0, "life": BEAM_TIME})
	else:
		var bolt := MeshInstance3D.new()
		var s := SphereMesh.new()
		s.radius = 0.35 if form == "MissileWeapon" else 0.2
		s.height = s.radius * 2.0
		bolt.mesh = s
		bolt.material_override = _glow(color, 4.0)
		bolt.position = from
		add_child(bolt)
		_live.append({"node": bolt, "kind": "fly", "t": 0.0, "life": flight, "from": from, "to": to})


func spawn_impact(at: Vector3, size: float = 1.0) -> void:
	var flash := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 1.0
	s.height = 2.0
	flash.mesh = s
	flash.material_override = _glow(Color(1.0, 0.7, 0.3), 6.0)
	flash.position = at
	flash.scale = Vector3.ONE * size
	add_child(flash)
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.6, 0.3)
	light.omni_range = 12.0 * size
	light.light_energy = 3.0
	flash.add_child(light)
	_live.append({"node": flash, "kind": "burst", "t": 0.0, "life": 0.35 * size, "size": size})


func _process(delta: float) -> void:
	var keep: Array[Dictionary] = []
	for e in _live:
		e["t"] += delta
		var k: float = clampf(e["t"] / e["life"], 0.0, 1.0)
		var node: Node3D = e["node"]
		match e["kind"]:
			"fade":
				(node as MeshInstance3D).transparency = k
			"fly":
				node.position = (e["from"] as Vector3).lerp(e["to"], k)
				if k >= 1.0:
					spawn_impact(e["to"], 0.5)
			"burst":
				node.scale = Vector3.ONE * e["size"] * (1.0 + 2.5 * k)
				(node as MeshInstance3D).transparency = k
		if e["t"] >= e["life"]:
			node.queue_free()
		else:
			keep.append(e)
	_live = keep


func _beam(from: Vector3, to: Vector3, color: Color, radius: float) -> MeshInstance3D:
	var beam := MeshInstance3D.new()
	var c := CylinderMesh.new()
	var length := from.distance_to(to)
	c.top_radius = radius
	c.bottom_radius = radius
	c.height = length
	c.radial_segments = 6
	beam.mesh = c
	beam.material_override = _glow(color, 5.0)
	add_child(beam)
	beam.global_position = (from + to) / 2.0
	var dir := (to - from).normalized()
	if absf(dir.dot(Vector3.UP)) < 0.999:
		beam.look_at(to, Vector3.UP)
		beam.rotate_object_local(Vector3.RIGHT, PI / 2.0)
	return beam


func _glow(color: Color, energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = energy
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m
