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
var ground_material: ShaderMaterial   # set by TerrainView: receives the canopy density map for the forest floor
var _canopy := PackedFloat32Array()
const CANOPY_CELL_M := 5.0
var _rng := RandomNumberGenerator.new()
var _palette := ""
var _apron: Image          # apron_sdf.png (R, 128 = the edge, above = paved): no cover on paving
var _snow: Image           # mask2.png (R = snow coverage): no cover on snowfields
var _ov: Array = []        # per-vertex overlay (road, runway) slots
var _gain := 1.0   # the map's albedo_gain (floored): scatter follows the ground's value, or pale pebbles sit on dark ground


func build(sim_map: SimMap, map_name: String, palette_layers: Array) -> void:
	map = sim_map
	_rng.seed = hash(map_name)
	var dir := "res://assets/terrain/v3/%s" % map_name
	if FileAccess.file_exists(dir.path_join("terrain_v3.json")):
		var inf: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("terrain_v3.json")))
		_gain = clampf(float(inf.get("albedo_gain", 1.0)), 0.3, 1.0)
		_palette = String(inf.get("palette", ""))
		_load_masks(dir)
	var means: Array[Color] = []
	for l in palette_layers:
		var c: Array = l["mean_albedo"]
		means.append(Color8(int(c[0]), int(c[1]), int(c[2])))
	if not OS.get_cmdline_user_args().has("--no-scatter"):
		var splat_img := (load(dir.path_join("splat.png")) as Texture2D).get_image()
		if splat_img.is_compressed():
			splat_img.decompress()
		_scatter(splat_img, means)
		if not OS.get_cmdline_user_args().has("--no-vegetation"):
			_vegetation(splat_img, means, map_name)
	if not OS.get_cmdline_user_args().has("--no-terrain-decals") and FileAccess.file_exists(dir.path_join("decals.json")):
		_decals(JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("decals.json"))))


# --- scatter -------------------------------------------------------------------------------------------------------

class Kind:
	var mesh: Mesh
	var range_m: float
	var chunk_m := CHUNK_M
	var mat: Material = null
	var fade := true
	var shadows := true
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
		"debris": _kind(_rock_mesh(3, 0.5), 420.0)}
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
					if _rng.randf() < 0.012:   # a few field stones
						_put(kinds[rocks[_rng.randi() % rocks.size()]], p, h, _rng.randf_range(0.4, 1.3), stone, 0.15)
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
	var key := Vector2i(floori((p.x + map.half_m) / k.chunk_m), floori((p.y + map.half_m) / k.chunk_m))
	if not k.chunks.has(key):
		k.chunks[key] = []
	var v := 1.0 + _rng.randf_range(-var_v, var_v)
	k.chunks[key].append([t, Color(col.r * v * _gain, col.g * v * _gain, col.b * v * _gain)])


var _scatter_material: ShaderMaterial


## One shared material for rocks, pebbles and debris: vertex colour albedo plus the ground's shadow_fill floor.
func _scatter_mat() -> ShaderMaterial:
	if _scatter_material == null:
		_scatter_material = ShaderMaterial.new()
		_scatter_material.shader = load("res://shaders/scatter_v3.gdshader")
		_scatter_material.set_shader_parameter("fill", ground_fill())
	return _scatter_material


## The ground's shadow_fill (palettes.json maps.<m>.shadow_fill, default 0.05): the floor every dressing material follows.
func ground_fill() -> float:
	if ground_material != null:
		var v: Variant = ground_material.get_shader_parameter("shadow_fill")
		if v != null:
			return float(v)
	return 0.05


func _commit(k: Kind, name_: String) -> int:
	var mat: Material = k.mat
	if mat == null:
		mat = _scatter_mat()
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
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if k.shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.visibility_range_end = k.range_m
		if k.fade:
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


# --- vegetation (terrain polish, 2026-11-01) ----------------------------------------------------------------------
# Ground cover: blade-clump cards (shaders/grass.gdshader, tools/art/terrain/grass_atlas.py) on the grass, ground and
# forest-floor classes, shrubs of the tree leaf atlas, and in the map's forests filler trees (the map's own HD tree
# models) between the placed trees, so a forest reads as a canopy and not as a scatter of single trees. The placed trees
# (objects.json) stay the only ones the sim knows: fillers and cover are scenery, passable and not destructible (the
# fillers are kept below 0.95 of the placed tree height, a mech walks through them like undergrowth).
# Everything is chunked MultiMeshes with a range, built from flat float buffers so a whole map's cover costs tens of MB.

const GRASS_RANGE := 320.0
const COVER_STEP := 2          # splat texels (2 m each) per cover cell
const FILLER_CELL_M := 16.0
const FILLER_STEP_M := 6.0

var _flat := {}   # Kind -> {Vector2i: PackedFloat32Array} (16 floats per instance: 3x4 transform rows + colour)
var veg_counts := {}
var plants_v3: TerrainPlantsV3   # understorey and shore dressing (terrain_plants_v3.gd), kept for the tests


func _flat_put(k: Kind, p: Vector2, h: float, size: float, stretch: float, yaw: float, col: Color, sink := 0.04) -> void:
	var key := Vector2i(floori((p.x + map.half_m) / k.chunk_m), floori((p.y + map.half_m) / k.chunk_m))
	if not _flat.has(k):
		_flat[k] = {}
	var d: Dictionary = _flat[k]
	if not d.has(key):
		d[key] = PackedFloat32Array()
	var c := cos(yaw) * size
	var sn := sin(yaw) * size
	var o := TerrainView.to_3d(p, h - sink * size)
	var buf: PackedFloat32Array = d[key]   # packed arrays are values: append, then store back
	buf.append_array(PackedFloat32Array([c, 0.0, sn, o.x, 0.0, size * stretch, 0.0, o.y, -sn, 0.0, c, o.z, col.r, col.g, col.b, 1.0]))
	d[key] = buf


func _flat_commit(name_: String) -> int:
	var total := 0
	for k in _flat:
		var kind: Kind = k
		var d: Dictionary = _flat[k]
		for key in d:
			var buf: PackedFloat32Array = d[key]
			var n := buf.size() / 16
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_colors = true
			mm.mesh = kind.mesh
			mm.instance_count = n
			mm.buffer = buf
			var mi := MultiMeshInstance3D.new()
			mi.name = "%s_%d_%d" % [name_, key.x, key.y]
			mi.multimesh = mm
			mi.material_override = kind.mat
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if kind.shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.visibility_range_end = kind.range_m
			if kind.fade:
				mi.visibility_range_end_margin = kind.range_m * 0.12
				mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			add_child(mi)
			total += n
	return total


## Ground-cover scale per palette: none on the moon, sparse on arid and industrial ground (round 2: black clumps on lunar
## dust and on city paving were the regression).
const COVER_SCALE := {"lunar": 0.0, "arid": 0.35, "industrial_grimy": 0.45, "industrial_grimy_dirt": 0.45}


func _load_masks(dir: String) -> void:
	if ResourceLoader.exists(dir.path_join("apron_sdf.png")):
		_apron = (load(dir.path_join("apron_sdf.png")) as Texture2D).get_image()
		if _apron.is_compressed():
			_apron.decompress()
	if ResourceLoader.exists(dir.path_join("mask2.png")):
		_snow = (load(dir.path_join("mask2.png")) as Texture2D).get_image()
		if _snow.is_compressed():
			_snow.decompress()
	_ov = map.meta.get("overlay_texture", [])


## Paving, roads and snowfields take no ground cover.
func _no_cover_at(p: Vector2) -> bool:
	var u := (p.x + map.half_m) / (map.half_m * 2.0)
	var v := (map.half_m - p.y) / (map.half_m * 2.0)
	if _apron != null:
		var a := _apron.get_pixel(clampi(int(u * _apron.get_width()), 0, _apron.get_width() - 1), clampi(int(v * _apron.get_height()), 0, _apron.get_height() - 1)).r
		if a > 112.0 / 255.0:   # inside, or within about 2 m outside the paved edge
			return true
	if _snow != null:
		if _snow.get_pixel(clampi(int(u * _snow.get_width()), 0, _snow.get_width() - 1), clampi(int(v * _snow.get_height()), 0, _snow.get_height() - 1)).r > 0.25:
			return true
	if not _ov.is_empty():
		var n := map.vertices_per_side
		var col := clampi(int(u * n), 0, n - 1)
		var row := clampi(int(v * n), 0, n - 1)
		var i := row * n + col
		if i < _ov.size() and int(_ov[i]) != 0 and int(_ov[i]) < 65535:   # 65535 = no overlay
			return true
	return false


## Canopy density of the placed trees (and later the fillers) on a coarse grid, for the forest floor: darker needle litter in
## the terrain shader, and more undergrowth where the canopy is.
func _canopy_n() -> int:
	return int(ceil(map.half_m * 2.0 / CANOPY_CELL_M))


func _canopy_stamp(p: Vector2, radius_m: float, weight: float) -> void:
	var n := _canopy_n()
	if _canopy.is_empty():
		_canopy.resize(n * n)
	var cx := (p.x + map.half_m) / CANOPY_CELL_M
	var cy := (map.half_m - p.y) / CANOPY_CELL_M
	var rc := radius_m / CANOPY_CELL_M
	for yy in range(maxi(int(cy - rc), 0), mini(int(cy + rc) + 1, n)):
		for xx in range(maxi(int(cx - rc), 0), mini(int(cx + rc) + 1, n)):
			var d := Vector2(xx + 0.5 - cx, yy + 0.5 - cy).length() / rc
			if d < 1.0:
				_canopy[yy * n + xx] += weight * (1.0 - d * d)


func _canopy_at(p: Vector2) -> float:
	if _canopy.is_empty():
		return 0.0
	var n := _canopy_n()
	var xx := clampi(int((p.x + map.half_m) / CANOPY_CELL_M), 0, n - 1)
	var yy := clampi(int((map.half_m - p.y) / CANOPY_CELL_M), 0, n - 1)
	return clampf(_canopy[yy * n + xx], 0.0, 1.0)


func _canopy_from_objects(map_name: String) -> void:
	var path := "res://data/maps/%s/objects.json" % map_name
	if not FileAccess.file_exists(path):
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var types: Dictionary = data["types"]
	for o in data["objects"]:
		var app := String((types.get(str(int(o["type"])), {}) as Dictionary).get("appearance", ""))
		if ResourceLoader.exists("res://assets/trees/%s.glb" % app) and not app.begins_with("palm"):
			_canopy_stamp(Vector2(float(o["x"]), float(o["y"])) * map.meters_per_wu, 7.5, 0.45)


func _canopy_publish() -> void:
	if ground_material == null or _canopy.is_empty():
		return
	var n := _canopy_n()
	var img := Image.create(n, n, false, Image.FORMAT_R8)
	for y in n:
		for x in n:
			img.set_pixel(x, y, Color(clampf(_canopy[y * n + x], 0.0, 1.0), 0, 0))
	var tex := ImageTexture.create_from_image(img)
	ground_material.set_shader_parameter("canopy", tex)
	ground_material.set_shader_parameter("has_canopy", true)


func _vegetation(splat: Image, means: Array[Color], map_name: String) -> void:
	var t0 := Time.get_ticks_msec()
	_canopy_from_objects(map_name)
	var grass_mat := ShaderMaterial.new()
	grass_mat.shader = load("res://shaders/grass.gdshader")
	grass_mat.set_shader_parameter("atlas", load("res://assets/terrain/v3/grass_atlas.png"))
	grass_mat.set_shader_parameter("fill", ground_fill())
	var leaf_mat: ShaderMaterial = (ObjectsView.tree_materials()[1] as ShaderMaterial).duplicate()   # own copy: only the shrubs get the night fill
	leaf_mat.set_shader_parameter("fill", ground_fill())
	var grass := []
	for i in 4:
		var k := _kind(_clump_mesh(i), GRASS_RANGE)
		k.chunk_m = 64.0
		k.mat = grass_mat
		k.shadows = false
		grass.append(k)
	var shrub := _kind(_shrub_mesh(), 420.0)
	shrub.chunk_m = 96.0
	shrub.mat = leaf_mat
	var n := splat.get_width()
	var px := map.half_m * 2.0 / n
	var water := map.water_level_m
	var grass_c := means[1]
	var ground_c := means[0]
	var forest_c := means[6]
	# 1) ground cover
	var rate := {1: 4.2, 0: 2.2, 6: 2.8}
	var cover_scale: float = COVER_SCALE.get(_palette, 1.0)
	var rng := _rng
	var patch_noise := FastNoiseLite.new()
	patch_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	patch_noise.fractal_octaves = 3
	patch_noise.frequency = 0.03
	patch_noise.seed = hash(map_name) & 0xffff
	var patch_noise2 := FastNoiseLite.new()
	patch_noise2.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	patch_noise2.frequency = 0.09
	patch_noise2.seed = (hash(map_name) >> 3) & 0xffff
	for r in range(0, n, COVER_STEP):
		for c in range(0, n, COVER_STEP):
			var cls := int(round(splat.get_pixel(c, r).r * 255.0))
			if not rate.has(cls):
				continue
			var pc := Vector2(-map.half_m + (c + 1) * px, map.half_m - (r + 1) * px)
			var patch := smoothstep(-0.08, 0.32, patch_noise.get_noise_2d(pc.x, pc.y)) * (0.6 + 0.4 * smoothstep(-0.2, 0.3, patch_noise2.get_noise_2d(pc.x, pc.y)))
			var cano := _canopy_at(pc)
			var cnt := int(rate[cls] * cover_scale * (2.0 * patch + 1.6 * cano) + rng.randf())   # clustered in patches with bare gaps, not an even speckle
			for _i in cnt:
				var p := Vector2(-map.half_m + (c + rng.randf() * COVER_STEP) * px, map.half_m - (r + rng.randf() * COVER_STEP) * px)
				if _no_cover_at(p):
					continue
				var h := map.height_at(p)
				var above := h - water if water > -100.0 else 99.0
				if above < 1.2 or (above < 3.5 and rng.randf() > (above - 1.2) / 2.3):
					continue
				var h2 := map.height_at(p + Vector2(2.5, 0.0))
				var h3 := map.height_at(p + Vector2(0.0, 2.5))
				if absf(h2 - h) > 1.9 or absf(h3 - h) > 1.9:
					continue
				var pick := rng.randf()
				var idx := 0 if pick < 0.38 else (1 if pick < 0.7 else (2 if pick < 0.86 else 3))
				var base := grass_c.lerp(ground_c, rng.randf_range(0.0, 0.55 if cls == 1 else 0.85))
				if cls == 6:
					base = base.lerp(forest_c, 0.4)
				var dry := rng.randf() < 0.1
				if dry:
					base = base.lerp(Color(0.62, 0.55, 0.30), 0.35)
				# close to the ground under it (the palette's own layer colours), a little lighter and greener: low contrast
				var tint := Color(0.26, 0.34, 0.17).lerp(Color(base.r * 1.5, base.g * 1.5, base.b * 1.5), 0.6) * _gain * rng.randf_range(0.78, 1.08)
				var sz := rng.randf_range(0.9, 1.9) * (1.2 if idx == 2 else 1.0)
				_flat_put(grass[idx], p, h, sz, rng.randf_range(0.8, 1.25), rng.randf() * TAU, tint)
	# 2) shrubs: scattered on grass/ground, denser on the forest floor
	var shrub_rate := {1: 0.05, 0: 0.025, 6: 0.14}
	for r in range(0, n, 4):
		for c in range(0, n, 4):
			var cls := int(round(splat.get_pixel(c, r).r * 255.0))
			if not shrub_rate.has(cls):
				continue
			var p := Vector2(-map.half_m + (c + rng.randf() * 4.0) * px, map.half_m - (r + rng.randf() * 4.0) * px)
			if cover_scale <= 0.0 or rng.randf() > shrub_rate[cls] * cover_scale * (1.0 + 5.0 * _canopy_at(p)) or _no_cover_at(p):
				continue
			var h := map.height_at(p)
			if water > -100.0 and h < water + 2.0:
				continue
			var base := grass_c.lerp(ground_c, 0.25)
			var tint := Color(0.46, 0.60, 0.30).lerp(Color(base.r * 2.0, base.g * 2.0, base.b * 2.0), 0.3) * _gain * rng.randf_range(0.6, 1.0)
			_flat_put(shrub, p, h, rng.randf_range(0.9, 2.2), rng.randf_range(0.7, 1.0), rng.randf() * TAU, tint, 0.1)
	var cover := _flat_commit("veg")
	veg_counts["cover"] = cover
	_flat.clear()
	# 3) filler trees
	var fillers := _fillers(splat, map_name)
	veg_counts["fillers"] = fillers
	_flat.clear()   # the fillers are committed; the plants start from an empty buffer set
	if TerrainPlantsV3.enabled():
		plants_v3 = TerrainPlantsV3.new()
		veg_counts["plants"] = plants_v3.build(self, splat, means, map_name)
	print("terrain dress: %d cover + shrub instances, %d filler trees (%d ms)" % [cover, fillers, Time.get_ticks_msec() - t0])


func _fillers(splat: Image, map_name: String) -> int:
	if OS.get_cmdline_user_args().has("--no-fillers"):
		return 0
	var path := "res://data/maps/%s/objects.json" % map_name
	if not FileAccess.file_exists(path):
		return 0
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var types: Dictionary = data["types"]
	var cell_n := {}      # Vector2i -> count of real trees
	var cell_apps := {}   # Vector2i -> {app: count}
	var real: Array[Vector2] = []
	var live_of := func(a: String) -> String:
		var b: String = a.trim_suffix("dead")
		if b.begins_with("willow") or b.begins_with("palm"):   # the willows' straw-yellow crowns multiply into yellow lollipops (mc2_11)
			return ""
		return b if ResourceLoader.exists("res://assets/trees/%s.glb" % b) else ""
	for o in data["objects"]:
		var t: Dictionary = types.get(str(int(o["type"])), {})
		var app := String(t.get("appearance", ""))
		if not ResourceLoader.exists("res://assets/trees/%s.glb" % app):
			continue
		var p := Vector2(float(o["x"]), float(o["y"])) * map.meters_per_wu
		real.append(p)
		var key := Vector2i(floori(p.x / FILLER_CELL_M), floori(p.y / FILLER_CELL_M))
		cell_n[key] = int(cell_n.get(key, 0)) + 1
		var live: String = live_of.call(app)
		if live != "":
			if not cell_apps.has(key):
				cell_apps[key] = {}
			cell_apps[key][live] = int((cell_apps[key] as Dictionary).get(live, 0)) + 1
	if real.is_empty():
		return 0
	var occ := {}   # 8 m hash of real trees and accepted fillers, for the spacing test
	var near := func(q: Vector2, d: float) -> bool:
		var kx := floori(q.x / 8.0)
		var ky := floori(q.y / 8.0)
		for dx in range(-1, 2):
			for dy in range(-1, 2):
				var arr: Array = occ.get(Vector2i(kx + dx, ky + dy), [])
				for e in arr:
					if (e as Vector2).distance_squared_to(q) < d * d:
						return true
		return false
	for q in real:
		var k8 := Vector2i(floori(q.x / 8.0), floori(q.y / 8.0))
		if not occ.has(k8):
			occ[k8] = []
		occ[k8].append(q)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(map_name) + 77
	var mats := ObjectsView.tree_materials()
	var kinds := {}   # app -> [bark Kind, leaf Kind]
	var n := splat.get_width()
	var px := map.half_m * 2.0 / n
	var water := map.water_level_m
	var made := 0
	var x := -map.half_m
	while x < map.half_m:
		var y := -map.half_m
		while y < map.half_m:
			var q := Vector2(x, y) + Vector2(rng.randf_range(-2.5, 2.5), rng.randf_range(-2.5, 2.5))
			y += FILLER_STEP_M
			var ck := Vector2i(floori(q.x / FILLER_CELL_M), floori(q.y / FILLER_CELL_M))
			var dens := 0
			var apps := {}
			for dx in range(-1, 2):
				for dy in range(-1, 2):
					var kk := Vector2i(ck.x + dx, ck.y + dy)
					dens += int(cell_n.get(kk, 0))
					if cell_apps.has(kk):
						for a in cell_apps[kk]:
							apps[a] = int(apps.get(a, 0)) + int(cell_apps[kk][a])
			if dens < 3 or apps.is_empty():
				continue
			if rng.randf() > clampf(float(dens - 2) / 8.0, 0.0, 1.0) * filler_density:
				continue
			if near.call(q, 5.0):
				continue
			var c := clampi(int((q.x + map.half_m) / px), 0, n - 1)
			var r := clampi(int((map.half_m - q.y) / px), 0, n - 1)
			var cls := int(round(splat.get_pixel(c, r).r * 255.0))
			if cls == 2 or cls == 3 or cls == 4 or cls == 7:
				continue
			var h := map.height_at(q)
			if water > -100.0 and h < water + 1.0:
				continue
			if absf(map.height_at(q + Vector2(3, 0)) - h) > 2.2 or absf(map.height_at(q + Vector2(0, 3)) - h) > 2.2:
				continue
			# species: weighted by the neighbourhood's own trees
			var tot := 0
			for a in apps:
				tot += int(apps[a])
			var pick := rng.randi() % tot
			var app := ""
			for a in apps:
				pick -= int(apps[a])
				if pick < 0:
					app = a
					break
			if not kinds.has(app):
				var scene: Node3D = load("res://assets/trees/%s.glb" % app).instantiate()
				var pair := []
				for i in 2:
					var mi := scene.find_child(["bark", "leaves"][i], true, false) as MeshInstance3D
					var kd := _kind(mi.mesh if mi else null, 1500.0)
					kd.chunk_m = 128.0
					kd.mat = mats[i]
					kd.fade = false
					pair.append(kd)
				scene.free()
				kinds[app] = pair
			var kp: Array = kinds[app]
			if kp[0].mesh == null and kp[1].mesh == null:
				continue
			var sc := rng.randf_range(0.5, 0.92)
			var yaw := rng.randf() * TAU
			var v := rng.randf_range(0.88, 1.1)
			for i in 2:
				if kp[i].mesh != null:
					_flat_put(kp[i], q, h, sc, 1.0, yaw, Color(v, v, v), 0.25)
			var k8 := Vector2i(floori(q.x / 8.0), floori(q.y / 8.0))
			if not occ.has(k8):
				occ[k8] = []
			occ[k8].append(q)
			_canopy_stamp(q, 6.0 * sc / 0.7, 0.4)
			made += 1
		x += FILLER_STEP_M
	_flat_commit("filler")
	_canopy_publish()
	return made


var filler_density := 1.0


func _clump_mesh(cell: int) -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var u0 := 0.25 * cell
	var u1 := u0 + 0.25
	for q in 3:
		var a := PI * q / 3.0
		var d := Vector3(cos(a), 0.0, sin(a)) * 0.6
		var up := Vector3(0.0, 1.15, 0.0)
		var pts := [-d, d, d + up, -d + up]
		var uvs := [Vector2(u0, 1.0), Vector2(u1, 1.0), Vector2(u1, 0.0), Vector2(u0, 0.0)]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.UP)
			st.set_color(Color(1, 1, 1))
			st.set_uv(uvs[i])
			st.add_vertex(pts[i])
	return st.commit()


## A shrub: a dome of leaf cards (the tree leaf atlas, broadleaf cell) with crown normals, lit as a volume.
func _shrub_mesh() -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r := RandomNumberGenerator.new()
	r.seed = 31337
	var centre := Vector3(0, 0.45, 0)
	for k in 16:
		var d := Vector3(r.randf_range(-1, 1), r.randf_range(0.0, 1.0), r.randf_range(-1, 1)).normalized()
		var p := centre + d * Vector3(0.55, 0.5, 0.55) * r.randf_range(0.5, 1.0)
		var right := d.cross(Vector3.UP)
		if right.length() < 0.1:
			right = Vector3.RIGHT
		right = right.normalized()
		var up := right.cross(d).normalized()
		var sz := r.randf_range(0.55, 0.85)
		var pts := [p - right * sz * 0.5 - up * sz * 0.5, p + right * sz * 0.5 - up * sz * 0.5, p + right * sz * 0.5 + up * sz * 0.5, p - right * sz * 0.5 + up * sz * 0.5]
		var uvs := [Vector2(0.5, 0.5), Vector2(1.0, 0.5), Vector2(1.0, 0.0), Vector2(0.5, 0.0)]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal((pts[i] - centre).normalized())
			st.set_color(Color(1, 1, 1))
			st.set_uv(uvs[i])
			st.add_vertex(pts[i])
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
