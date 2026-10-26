class_name TerrainDressV3
extends Node3D
## T5/T6 for the v3 terrain (brought forward in the T3 review, 2026-10-25; only with TerrainV3.enabled): scatter
## (rocks on rock and cliff ground, debris on scree and aprons, grass tufts and bushes on grass and forest floor) and
## ground decals (tyre tracks along roads, oil near buildings, grime along apron edges, old craters and scorch).
## Scatter is placed from the map's splat (res://assets/terrain/v3/<map>/splat.png) with a fixed seed, on the sim's
## own heights (SimMap.height_at), in 160 m chunks with a camera-distance fade; decals come from decals.json
## (tools/art/terrain/terrain_dress.py). Everything is procedural or this project's own: no third-party meshes.

const CHUNK_M := 160.0
const TERRAIN_LAYER := 2

var map: SimMap
var _rng := RandomNumberGenerator.new()
var _gain := 1.0   # the map's albedo_gain (floored): scatter follows the ground's value, or pale pebbles sit on dark ground


func build(sim_map: SimMap, map_name: String, palette_layers: Array) -> void:
	map = sim_map
	_rng.seed = hash(map_name)
	var dir := "res://assets/terrain/v3/%s" % map_name
	if FileAccess.file_exists(dir.path_join("terrain_v3.json")):
		var inf: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("terrain_v3.json")))
		_gain = clampf(float(inf.get("albedo_gain", 1.0)), 0.3, 1.0)
	var means: Array[Color] = []
	for l in palette_layers:
		var c: Array = l["mean_albedo"]
		means.append(Color8(int(c[0]), int(c[1]), int(c[2])))
	if not OS.get_cmdline_user_args().has("--no-scatter"):
		_scatter((load(dir.path_join("splat.png")) as Texture2D).get_image(), means)
	if not OS.get_cmdline_user_args().has("--no-terrain-decals") and FileAccess.file_exists(dir.path_join("decals.json")):
		_decals(JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("decals.json"))))


# --- scatter -------------------------------------------------------------------------------------------------------

class Kind:
	var mesh: Mesh
	var range_m: float
	var chunks := {}   # Vector2i -> Array of [Transform3D, Color]


func _scatter(splat: Image, means: Array[Color]) -> void:
	if splat.is_compressed():
		splat.decompress()
	var n := splat.get_width()
	var side := map.half_m * 2.0
	var px := side / n
	var kinds := {
		"rock": _kind(_rock_mesh(1, 0.62), 650.0), "rock2": _kind(_rock_mesh(2, 0.45), 650.0), "rock3": _kind(_rock_mesh(5, 0.8), 650.0),
		"slab": _kind(_rock_mesh(7, 0.3), 650.0),
		"debris": _kind(_rock_mesh(3, 0.5), 420.0), "tuft": _kind(_tuft_mesh(), 300.0), "bush": _kind(_bush_mesh(), 520.0)}
	# stone colour: the rock and scree layers' means, greyed and grimed a little (never the grass layer)
	var stone := means[2].lerp(means[4], 0.4).lerp(Color(0.42, 0.40, 0.37), 0.35)
	var rocks := ["rock", "rock2", "rock3", "slab"]
	var water := map.water_level_m
	var step := 3  # sample every 3 splat texels (about 6 m)
	for r in range(0, n, step):
		for c in range(0, n, step):
			var cls := int(round(splat.get_pixel(c, r).r * 255.0))
			var p := Vector2(-map.half_m + (c + _rng.randf() * step) * px, map.half_m - (r + _rng.randf() * step) * px)
			var h := map.height_at(p)
			if water > -100.0 and h < water + 0.3:
				continue
			match cls:
				2, 3:   # rock, cliff
					if _rng.randf() < 0.30:
						_put(kinds[rocks[_rng.randi() % rocks.size()]], p, h, _rng.randf_range(0.6, 2.8) * (1.6 if _rng.randf() < 0.1 else 1.0), stone.darkened(_rng.randf_range(0.0, 0.25)), 0.15)
				4:      # scree, aprons, verges
					if _rng.randf() < 0.22:
						_put(kinds["debris"], p, h, _rng.randf_range(0.25, 0.8), stone.lerp(means[4], 0.5).darkened(0.1), 0.2)
				5:      # dust
					if _rng.randf() < 0.04:
						_put(kinds["debris"], p, h, _rng.randf_range(0.3, 0.7), stone, 0.15)
				0, 1, 6:
					if _rng.randf() < 0.55:
						var g := means[1].lerp(means[0], _rng.randf_range(0.0, 0.6)) if cls != 6 else means[6].lerp(means[1], 0.5)
						_put(kinds["tuft"], p, h, _rng.randf_range(0.5, 1.1), g, 0.15)
					if _rng.randf() < 0.012:   # a few field stones
						_put(kinds[rocks[_rng.randi() % rocks.size()]], p, h, _rng.randf_range(0.4, 1.3), stone, 0.15)
					if _rng.randf() < (0.03 if cls == 6 else 0.008):
						var bc := means[1].lerp(Color(0.2, 0.2, 0.15), 0.5).darkened(0.3)
						_put(kinds["bush"], p + Vector2(_rng.randf() - 0.5, _rng.randf() - 0.5) * 3.0, h, _rng.randf_range(0.8, 1.8), bc, 0.12)
	var total := 0
	for k in kinds:
		total += _commit(kinds[k], String(k))
	print("terrain dress: %d scatter instances" % total)


func _kind(mesh: Mesh, range_m: float) -> Kind:
	var k := Kind.new()
	k.mesh = mesh
	k.range_m = range_m
	return k


func _put(k: Kind, p: Vector2, h: float, size: float, col: Color, var_v: float) -> void:
	var b := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3(size, size * _rng.randf_range(0.7, 1.1), size))
	var t := Transform3D(b, TerrainView.to_3d(p, h - 0.05 * size))
	var key := Vector2i(floori((p.x + map.half_m) / CHUNK_M), floori((p.y + map.half_m) / CHUNK_M))
	if not k.chunks.has(key):
		k.chunks[key] = []
	var v := 1.0 + _rng.randf_range(-var_v, var_v)
	k.chunks[key].append([t, Color(col.r * v * _gain, col.g * v * _gain, col.b * v * _gain)])


func _commit(k: Kind, name_: String) -> int:
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.92
	if name_ == "tuft":
		mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	var total := 0
	for key in k.chunks:
		var items: Array = k.chunks[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = k.mesh
		mm.instance_count = items.size()
		for i in items.size():
			mm.set_instance_transform(i, items[i][0])
			mm.set_instance_color(i, items[i][1])
		var mi := MultiMeshInstance3D.new()
		mi.name = "%s_%d_%d" % [name_, key.x, key.y]
		mi.multimesh = mm
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if name_ == "tuft" else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		mi.visibility_range_end = k.range_m
		mi.visibility_range_end_margin = k.range_m * 0.15
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		add_child(mi)
		total += items.size()
	return total


func _rock_mesh(seed_: int, flat := 0.62) -> Mesh:
	var r := RandomNumberGenerator.new()
	r.seed = seed_ * 7919
	var sm := SphereMesh.new()
	sm.radial_segments = 9
	sm.rings = 5
	var arr := sm.get_mesh_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var lumps: Array[Vector3] = []
	for i in 4 + seed_ % 4:
		lumps.append(Vector3(r.randf_range(-1, 1), r.randf_range(-0.3, 1), r.randf_range(-1, 1)).normalized())
	for i in v.size():
		var d := v[i].normalized()
		var s := 0.5
		for l in lumps:
			s += 0.12 * maxf(d.dot(l), 0.0)
		s *= 1.0 + r.randf_range(-0.06, 0.06)
		v[i] = Vector3(d.x * s * (1.0 + 0.3 * float(seed_ % 3 == 0)), maxf(d.y * s * flat, -0.1), d.z * s)
	return _flat_mesh(v, arr[Mesh.ARRAY_INDEX])


func _bush_mesh() -> Mesh:
	var r := RandomNumberGenerator.new()
	r.seed = 4242
	var sm := SphereMesh.new()
	sm.radial_segments = 10
	sm.rings = 6
	var arr := sm.get_mesh_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i in v.size():
		var d := v[i].normalized()
		var s := 0.5 * (1.0 + r.randf_range(-0.22, 0.22))
		v[i] = Vector3(d.x * s, (d.y * 0.7 + 0.3) * s, d.z * s)
	return _flat_mesh(v, arr[Mesh.ARRAY_INDEX])


func _tuft_mesh() -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r := RandomNumberGenerator.new()
	r.seed = 99
	for i in 7:
		var a := TAU * i / 7.0 + r.randf_range(-0.3, 0.3)
		var lean := Vector3(cos(a), 0, sin(a)) * r.randf_range(0.15, 0.4)
		var w := Vector3(-sin(a), 0, cos(a)) * 0.05
		var top := lean + Vector3(0, r.randf_range(0.5, 0.9), 0)
		st.set_color(Color(0.8, 0.8, 0.8))
		st.add_vertex(-w)
		st.add_vertex(w)
		st.set_color(Color(1.15, 1.15, 1.05))
		st.add_vertex(top)
	st.generate_normals()
	return st.commit()


func _flat_mesh(v: PackedVector3Array, idx: PackedInt32Array) -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_color(Color(1, 1, 1))
	for i in idx:
		st.add_vertex(v[i])
	st.generate_normals()
	return st.commit()


# --- decals --------------------------------------------------------------------------------------------------------

func _decals(items: Array) -> void:
	var tex := {"tracks": load("res://assets/terrain/v3/decals/tracks.png"), "oil": load("res://assets/terrain/v3/decals/oil.png"),
		"grime": load("res://assets/terrain/v3/decals/grime.png"), "scorch": load("res://assets/decals/scorch.png")}
	var craters: Array = []
	for i in 4:
		var p := "res://assets/decals/crater_%d.png" % i
		if ResourceLoader.exists(p):
			craters.append(load(p))
	var count := 0
	for d in items:
		var kind := String(d["t"])
		var t: Texture2D = craters[int(d.get("v", 0)) % craters.size()] if kind == "crater" and not craters.is_empty() else tex.get(kind)
		if t == null:
			continue
		var p := Vector2(float(d["x"]), float(d["y"]))
		var w := float(d["w"])
		var l := float(d["l"]) if float(d["l"]) > 0.0 else w
		var dec := Decal.new()
		dec.texture_albedo = t
		dec.size = Vector3(w, 6.0, l)
		dec.cull_mask = 1 << (TERRAIN_LAYER - 1)
		dec.albedo_mix = 1.0
		dec.modulate = Color(1, 1, 1, 0.85 if kind != "crater" else 0.9)
		dec.distance_fade_enabled = true
		dec.distance_fade_begin = 420.0
		dec.distance_fade_length = 120.0
		dec.upper_fade = 0.3
		dec.lower_fade = 0.3
		var a := deg_to_rad(float(d["yaw"]))
		var along := Vector3(cos(a), 0, -sin(a))
		dec.position = TerrainView.to_3d(p, map.height_at(p))
		dec.rotation.y = atan2(along.x, along.z)
		add_child(dec)
		count += 1
	print("terrain dress: %d decals" % count)
