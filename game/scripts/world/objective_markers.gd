class_name ObjectiveMarkers
extends Node3D
## 3D beacons over active objectives that display a marker (DisplayMarker):
## a slowly pulsing light column with a ground ring.

var objectives: SimObjectives
var map: SimMap
var _beacons: Dictionary = {}  # objective index -> Node3D


func setup(sim_objectives: SimObjectives, sim_map: SimMap) -> void:
	objectives = sim_objectives
	map = sim_map


func _process(_delta: float) -> void:
	var live := {}
	for obj in objectives.visible_objectives():
		if obj["complete"] or not obj["show_marker"]:
			continue
		live[obj["index"]] = true
		if not _beacons.has(obj["index"]):
			_beacons[obj["index"]] = _make(obj["marker"])
	for i in _beacons.keys():
		if not live.has(i):
			_beacons[i].queue_free()
			_beacons.erase(i)
	var pulse := 0.6 + 0.4 * sin(Time.get_ticks_msec() / 300.0)
	for b in _beacons.values():
		(b.get_child(0) as MeshInstance3D).transparency = 1.0 - 0.55 * pulse


func _make(pos: Vector2) -> Node3D:
	var root := Node3D.new()
	root.position = TerrainView.to_3d(pos, map.height_at(pos))
	var col := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 1.5
	cyl.bottom_radius = 2.5
	cyl.height = 120.0
	col.mesh = cyl
	col.position.y = 60.0
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(1.0, 0.85, 0.2)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.emission_enabled = true
	m.emission = Color(1.0, 0.8, 0.2)
	col.material_override = m
	col.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(col)
	var ring := MeshInstance3D.new()
	var t := TorusMesh.new()
	t.inner_radius = 14.0
	t.outer_radius = 15.5
	ring.mesh = t
	ring.position.y = 0.5
	ring.material_override = m
	root.add_child(ring)
	add_child(root)
	return root
