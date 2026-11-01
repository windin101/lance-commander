class_name TerrainPlantsV3
extends RefCounted
## Understorey and shore dressing for the v3 terrain (terrain polish round 3, 2026-11-01), built by TerrainDressV3 after the
## ground cover and the filler trees. Scenery only: units walk through it, nothing here is known to the sim.
##
##  * thickets: bushes with ferns and a few flowers in clumps (habitat noise picks the patches; bare gaps between), more
##    ferns under the canopy, none on rock, scree, snow, roads, paving or lunar ground
##  * forest-edge understorey: bushes and ferns where the canopy density thins (0.1-0.5)
##  * hedgerows: chains of elongated bushes along the paved edge (offset off it) and along the boundary between meadow and
##    bare ground, in stretches with gaps, never across a road or into a footprint
##  * wildflower meadows: their own patches on grass, never speckle
##  * shore: reed clumps standing at the water's edge, pebbles and a few rocks along the waterline
##  * per palette: temperate gets all of it, moorland dark shrubs, ferns and gorse flowers, stony and arid dry scrub, snow a
##    few dark shrubs, industrial a little scrub, lunar nothing
## Meshes are cards and domes of plants_atlas.png (tools/art/terrain/plants_atlas.py); instances are chunked MultiMeshes with
## a visibility range, built from the dress's flat float buffers.

const RANGE_BUSH := 460.0
const RANGE_HEDGE := 700.0
const RANGE_FERN := 300.0
const RANGE_FLOWER := 280.0
const RANGE_SCRUB := 420.0
const CHUNK := 128.0
const MAX_BUSH := 9000
const MAX_FERN := 12000
const MAX_FLOWER := 14000
const MAX_HEDGE := 4500

## Per palette weights: bush, fern, flower, scrub, hedge, understorey, reed, pebble, tint (the foliage colour family).
const BIOMES := {
	"temperate_muted": {"bush": 1.0, "fern": 1.0, "flower": 1.0, "scrub": 0.1, "hedge": 1.0, "under": 1.0, "reed": 1.0, "pebble": 1.0, "dark": 0.0},
	"moorland": {"bush": 0.55, "fern": 0.9, "flower": 0.35, "scrub": 0.5, "hedge": 0.25, "under": 0.7, "reed": 0.7, "pebble": 1.0, "dark": 0.45},
	"stony": {"bush": 0.3, "fern": 0.2, "flower": 0.12, "scrub": 0.9, "hedge": 0.1, "under": 0.45, "reed": 0.55, "pebble": 1.0, "dark": 0.25},
	"arid": {"bush": 0.0, "fern": 0.0, "flower": 0.04, "scrub": 0.9, "hedge": 0.0, "under": 0.3, "reed": 0.12, "pebble": 0.8, "dark": 0.0},
	"industrial_grimy": {"bush": 0.0, "fern": 0.0, "flower": 0.0, "scrub": 0.22, "hedge": 0.0, "under": 0.0, "reed": 0.15, "pebble": 0.5, "dark": 0.2},
	"industrial_grimy_dirt": {"bush": 0.0, "fern": 0.0, "flower": 0.0, "scrub": 0.3, "hedge": 0.0, "under": 0.0, "reed": 0.15, "pebble": 0.5, "dark": 0.2},
	"snow": {"bush": 0.35, "fern": 0.0, "flower": 0.0, "scrub": 0.25, "hedge": 0.0, "under": 0.2, "reed": 0.0, "pebble": 0.6, "dark": 0.7},
	"snow_white": {"bush": 0.35, "fern": 0.0, "flower": 0.0, "scrub": 0.25, "hedge": 0.0, "under": 0.2, "reed": 0.0, "pebble": 0.6, "dark": 0.7},
	"lunar": {"bush": 0.0, "fern": 0.0, "flower": 0.0, "scrub": 0.0, "hedge": 0.0, "under": 0.0, "reed": 0.0, "pebble": 0.0, "dark": 0.0},
}

var d: TerrainDressV3
var map: SimMap
var rng := RandomNumberGenerator.new()
var biome: Dictionary
var counts := {}
var _splat: Image
var _n := 0
var _px := 1.0
var _water := -1000.0
var _foot := {}                   # 32 m hash of non-tree object footprints: Vector2i -> Array[Vector3(x, y, radius)]
var _trees := {}                  # 16 m hash of tree positions (to keep bushes off trunks)
var _mat_card: ShaderMaterial
var _mat_dome: ShaderMaterial
var _mat_flower: ShaderMaterial
var _mat_reed: ShaderMaterial
var _kinds := {}
var _n_bush := 0
var _n_fern := 0
var _n_flower := 0
var _n_hedge := 0
var _tint_leaf := Color(0.30, 0.42, 0.20)
var _tint_dry := Color(0.5, 0.45, 0.32)
var _pg := 1.0                    # the albedo gain, softened: plants stay lighter than the darkened ground under them
var _hab: FastNoiseLite
var _hab2: FastNoiseLite
var _meadow: FastNoiseLite
var _gate: FastNoiseLite


static func biome_for(palette: String) -> Dictionary:
	return BIOMES.get(palette, BIOMES["temperate_muted"])


static func enabled() -> bool:
	return not OS.get_cmdline_user_args().has("--no-plants") and OS.get_environment("MC2_PLANTS") != "0"


# --- meshes --------------------------------------------------------------------------------------------------------

## `cards` crossed upright cards of a cell, w wide and h tall, base at y = 0; normals bent up (the shader mixes more).
static func cards_mesh(cell: int, cards: int, w: float, h: float, lean := 0.0) -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for q in cards:
		var a := PI * q / cards
		var dir := Vector3(cos(a), 0.0, sin(a)) * w * 0.5
		var out := Vector3(-sin(a), 0.0, cos(a)) * lean * h
		var pts := [-dir, dir, dir + Vector3(0, h, 0) + out, -dir + Vector3(0, h, 0) + out]
		var uvs := [Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.UP)
			st.set_uv(uvs[i])
			st.set_uv2(Vector2(float(cell), 1.0))
			st.add_vertex(pts[i])
	return st.commit()


## A lumpy dome of leaf-mass texture (the cell tiles `rep` times round it): radius 0.55, height 0.62, flat at y = 0.
static func dome_mesh(seed_: int, segs := 12, rings := 5, rep := 3.0) -> Mesh:
	var r := RandomNumberGenerator.new()
	r.seed = seed_
	var lump: Array = []
	for i in rings + 1:
		var row := []
		for j in segs:
			row.append(r.randf_range(0.8, 1.16))
		lump.append(row)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var grid: Array = []
	for i in rings + 1:
		var lat := float(i) / rings * PI * 0.5
		var gr: Array = []
		for j in segs + 1:
			var lon := float(j % segs) / segs * TAU
			var k: float = lump[i][j % segs] * (1.0 if i < rings else 0.7)
			var p := Vector3(cos(lon) * cos(lat) * 0.55, sin(lat) * 0.62, sin(lon) * cos(lat) * 0.55) * k
			gr.append([p, Vector2(float(j) / segs, 1.0 - float(i) / rings)])
		grid.append(gr)
	for i in rings:
		for j in segs:
			var a: Array = grid[i][j]
			var b: Array = grid[i][j + 1]
			var c: Array = grid[i + 1][j + 1]
			var dd: Array = grid[i + 1][j]
			for v in [a, b, c, a, c, dd]:
				var p: Vector3 = v[0]
				st.set_normal((p - Vector3(0, 0.08, 0)).normalized())
				st.set_uv(v[1])
				st.set_uv2(Vector2(2.0, rep))
				st.add_vertex(p)
	return st.commit()


# --- build ---------------------------------------------------------------------------------------------------------

func _make_materials() -> void:
	var atlas := load("res://assets/terrain/v3/plants_atlas.png") as Texture2D
	var sh := load("res://shaders/plants.gdshader") as Shader
	_mat_card = ShaderMaterial.new()
	_mat_card.shader = sh
	_mat_card.set_shader_parameter("atlas", atlas)
	_mat_card.set_shader_parameter("up_mix", 0.7)
	_mat_dome = ShaderMaterial.new()
	_mat_dome.shader = sh
	_mat_dome.set_shader_parameter("atlas", atlas)
	_mat_dome.set_shader_parameter("up_mix", 0.12)
	_mat_dome.set_shader_parameter("wind", 0.18)
	_mat_flower = ShaderMaterial.new()
	_mat_flower.shader = sh
	_mat_flower.set_shader_parameter("atlas", atlas)
	_mat_flower.set_shader_parameter("up_mix", 0.8)
	_mat_flower.set_shader_parameter("far_fade_start", 60.0)
	_mat_flower.set_shader_parameter("far_fade_end", 180.0)
	_mat_reed = ShaderMaterial.new()
	_mat_reed.shader = load("res://shaders/grass.gdshader")
	_mat_reed.set_shader_parameter("atlas", load("res://assets/terrain/v3/grass_atlas.png"))
	_mat_reed.set_shader_parameter("wind", 0.35)
	for m in [_mat_card, _mat_dome, _mat_flower, _mat_reed]:
		m.set_shader_parameter("fill", d.ground_fill())
	for m in [_mat_card, _mat_dome, _mat_flower, _mat_reed]:
		m.set_shader_parameter("fill_tint", d.plant_fill_tint)


func _kind(key: String, mesh: Mesh, range_m: float, mat: Material, shadows: bool) -> TerrainDressV3.Kind:
	if _kinds.has(key):
		return _kinds[key]
	var k := d._kind(mesh, range_m)
	k.chunk_m = CHUNK
	k.mat = mat
	k.shadows = shadows
	_kinds[key] = k
	return k


func _noise(freq: float, seed_: int, octaves := 2) -> FastNoiseLite:
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	n.fractal_octaves = octaves
	n.frequency = freq
	n.seed = seed_ & 0xffff
	return n


## The class (splat red, 0 ground, 1 grass, 2 rock, 3 cliff, 4 scree, 5 dust, 6 forest floor, 7 water bed).
func _cls(p: Vector2) -> int:
	var c := clampi(int((p.x + map.half_m) / _px), 0, _n - 1)
	var r := clampi(int((map.half_m - p.y) / _px), 0, _n - 1)
	return int(round(_splat.get_pixel(c, r).r * 255.0))


func _near_footprint(p: Vector2, extra := 0.0) -> bool:
	var kx := floori(p.x / 32.0)
	var ky := floori(p.y / 32.0)
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			var arr: Array = _foot.get(Vector2i(kx + dx, ky + dy), [])
			for e in arr:
				var v: Vector3 = e
				if Vector2(v.x, v.y).distance_squared_to(p) < (v.z + extra) * (v.z + extra):
					return true
	return false


func _near_tree(p: Vector2, dist: float) -> bool:
	var kx := floori(p.x / 16.0)
	var ky := floori(p.y / 16.0)
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			var arr: Array = _trees.get(Vector2i(kx + dx, ky + dy), [])
			for e in arr:
				if (e as Vector2).distance_squared_to(p) < dist * dist:
					return true
	return false


func _load_objects(map_name: String) -> void:
	var path := "res://data/maps/%s/objects.json" % map_name
	if not FileAccess.file_exists(path):
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var types: Dictionary = data["types"]
	for o in data["objects"]:
		var t: Dictionary = types.get(str(int(o["type"])), {})
		var app := String(t.get("appearance", ""))
		var p := Vector2(float(o["x"]), float(o["y"])) * map.meters_per_wu
		if ResourceLoader.exists("res://assets/trees/%s.glb" % app):
			var k16 := Vector2i(floori(p.x / 16.0), floori(p.y / 16.0))
			if not _trees.has(k16):
				_trees[k16] = []
			_trees[k16].append(p)
			continue
		var r := maxf(2.5, float(t.get("extent_radius", 0.0)) * map.meters_per_wu) + 1.5
		var k32 := Vector2i(floori(p.x / 32.0), floori(p.y / 32.0))
		if not _foot.has(k32):
			_foot[k32] = []
		_foot[k32].append(Vector3(p.x, p.y, r))


## A plant may stand here: the right class, off paving and roads and snow, dry, gentle, off footprints and trunks.
func _ok(p: Vector2, classes: Array, min_above := 1.0, max_slope := 1.7, tree_clear := 1.6) -> bool:
	if absf(p.x) > map.half_m - 8.0 or absf(p.y) > map.half_m - 8.0:
		return false
	if not classes.has(_cls(p)):
		return false
	if d._no_cover_at(p):
		return false
	var h := map.height_at(p)
	if _water > -100.0 and h < _water + min_above:
		return false
	if absf(map.height_at(p + Vector2(2.5, 0.0)) - h) > max_slope or absf(map.height_at(p + Vector2(0.0, 2.5)) - h) > max_slope:
		return false
	if _near_footprint(p):
		return false
	if tree_clear > 0.0 and _near_tree(p, tree_clear):
		return false
	return true


## Instance with separate scale along (sx), up (sy) and across (sz) the yaw direction.
func _put3(k: TerrainDressV3.Kind, p: Vector2, h: float, sx: float, sy: float, sz: float, yaw: float, col: Color, sink := 0.08) -> void:
	var key := Vector2i(floori((p.x + map.half_m) / k.chunk_m), floori((p.y + map.half_m) / k.chunk_m))
	if not d._flat.has(k):
		d._flat[k] = {}
	var dd: Dictionary = d._flat[k]
	if not dd.has(key):
		dd[key] = PackedFloat32Array()
	var c := cos(yaw)
	var s := sin(yaw)
	var o := TerrainView.to_3d(p, h - sink * sy)
	var buf: PackedFloat32Array = dd[key]
	buf.append_array(PackedFloat32Array([c * sx, 0.0, s * sz, o.x, 0.0, sy, 0.0, o.y, -s * sx, 0.0, c * sz, o.z, col.r, col.g, col.b, 1.0]))
	dd[key] = buf


func _leaf_col(var_v := 0.2) -> Color:
	var c := _tint_leaf.lerp(Color(0.22, 0.26, 0.18), biome.get("dark", 0.0))
	var v := 1.0 + rng.randf_range(-var_v, var_v)
	return Color(c.r * v, c.g * v * rng.randf_range(0.92, 1.08), c.b * v) * _pg


func _dry_col() -> Color:
	var v := rng.randf_range(0.8, 1.15)
	return Color(_tint_dry.r * v, _tint_dry.g * v, _tint_dry.b * v) * _pg


func _bush(p: Vector2, size: float, dry := false, stretch := 1.0, yaw := -1.0) -> void:
	if _n_bush >= MAX_BUSH:
		return
	var h := map.height_at(p)
	var v := rng.randi() % 3
	if dry:
		var ks := _kind("scrub%d" % v, dome_mesh(41 + v * 5, 10, 4), RANGE_SCRUB, _mat_dome, true)   # a rounded dome, not crossed cards
		_put3(ks, p, h, size * 0.9, size * rng.randf_range(0.55, 0.85), size * 0.9, rng.randf() * TAU, _dry_col())
	else:
		var kd := _kind("bush%d" % v, dome_mesh(11 + v * 7), RANGE_BUSH, _mat_dome, true)
		var yw := rng.randf() * TAU if yaw < 0.0 else yaw
		_put3(kd, p, h, size * stretch, size * rng.randf_range(0.8, 1.2), size, yw, _leaf_col())
	_n_bush += 1


func _fern(p: Vector2, size: float) -> void:
	if _n_fern >= MAX_FERN:
		return
	var k := _kind("fern", cards_mesh(0, 3, 1.5, 1.05, 0.25), RANGE_FERN, _mat_card, false)
	d._flat_put(k, p, map.height_at(p), size, rng.randf_range(0.8, 1.2), rng.randf() * TAU, _leaf_col(0.25) * 1.1, 0.05)
	_n_fern += 1


func _flower(p: Vector2, size: float) -> void:
	if _n_flower >= MAX_FLOWER:
		return
	var k := _kind("flower", cards_mesh(1, 3, 1.2, 0.95, 0.0), RANGE_FLOWER, _mat_flower, false)
	var v := rng.randf_range(0.42, 0.55) * _pg
	d._flat_put(k, p, map.height_at(p), size, rng.randf_range(0.85, 1.2), rng.randf() * TAU, Color(v, v, v * 0.95), 0.04)
	_n_flower += 1


func build(dress: TerrainDressV3, splat: Image, means: Array[Color], map_name: String) -> Dictionary:
	d = dress
	map = dress.map
	if not enabled():
		return counts
	biome = biome_for(dress._palette)
	var t0 := Time.get_ticks_msec()
	rng.seed = hash(map_name) + 909
	_splat = splat
	_n = splat.get_width()
	_px = map.half_m * 2.0 / _n
	_water = map.water_level_m
	_pg = pow(d._gain, 0.55)
	_load_objects(map_name)
	_make_materials()
	var seed_ := hash(map_name)
	_hab = _noise(0.011, seed_ + 1)
	_hab2 = _noise(0.035, seed_ + 2, 3)
	_meadow = _noise(0.017, seed_ + 3)
	_gate = _noise(0.0085, seed_ + 4)
	# the palette's own greens, for the foliage tint; brown and grey ground gets olive, dry plants take the dust colour
	var g := means[1]
	var gnd := means[0]
	_tint_leaf = Color(0.40, 0.48, 0.30).lerp(Color(g.r * 2.0, g.g * 2.1, g.b * 1.8), 0.2)
	_tint_dry = Color(0.42, 0.45, 0.32).lerp(Color(gnd.r * 2.0, gnd.g * 1.9, gnd.b * 1.6), 0.2)
	if biome.get("dark", 0.0) > 0.0:
		_tint_dry = _tint_dry.lerp(Color(0.3, 0.28, 0.24), biome["dark"] * 0.6)
	var tp := Time.get_ticks_msec()
	_thickets()
	print("plants: thickets %d ms" % (Time.get_ticks_msec() - tp))
	_meadows()
	print("plants: meadows %d ms" % (Time.get_ticks_msec() - tp))
	if biome["under"] > 0.0:
		_understorey()
	print("plants: understorey %d ms" % (Time.get_ticks_msec() - tp))
	if biome["hedge"] > 0.0 and not OS.get_cmdline_user_args().has("--no-hedges"):
		_hedges(map_name)
	print("plants: hedges %d ms" % (Time.get_ticks_msec() - tp))
	var total: int = d._flat_commit("plant")
	d._flat.clear()
	var shore := 0
	if _water > -100.0 and not OS.get_cmdline_user_args().has("--no-shore-dress"):
		shore = _shore(means)
	counts = {"bush": _n_bush, "fern": _n_fern, "flower": _n_flower, "hedge": _n_hedge, "shore": shore, "total": total + shore}
	print("terrain plants: %s (%d ms)" % [str(counts), Time.get_ticks_msec() - t0])
	return counts


# --- thickets and meadows ------------------------------------------------------------------------------------------

func _thickets() -> void:
	var w_bush: float = biome["bush"]
	var w_fern: float = biome["fern"]
	var w_scrub: float = biome["scrub"]
	if w_bush + w_scrub <= 0.0:
		return
	var cell := 22.0
	var gx := -map.half_m
	while gx < map.half_m:
		var gy := -map.half_m
		while gy < map.half_m:
			var p := Vector2(gx + rng.randf() * cell, gy + rng.randf() * cell)
			gy += cell
			var hab := _hab.get_noise_2d(p.x, p.y)
			var q := smoothstep(0.02, 0.4, hab) * (0.55 + 0.45 * smoothstep(-0.1, 0.3, _hab2.get_noise_2d(p.x, p.y)))
			if rng.randf() > q * 0.62:
				continue
			if not _ok(p, [0, 1, 5, 6], 1.5, 1.4):
				continue
			var cls := _cls(p)
			var dry := rng.randf() < w_scrub / maxf(0.001, w_bush + w_scrub) or cls == 5
			if not dry and rng.randf() > w_bush:
				continue
			var r := rng.randf_range(4.5, 11.0)
			if OS.get_cmdline_user_args().has("--plants-debug") and _n_bush % 7 == 0:
				print("thicket %s dry=%s" % [p.snapped(Vector2(1, 1)), dry])
			var nb := 2 + int(rng.randf() * 5.0 * clampf(q + 0.3, 0.0, 1.0))
			for i in nb:
				var o := Vector2(rng.randfn(0.0, r * 0.45), rng.randfn(0.0, r * 0.45))
				if not _ok(p + o, [0, 1, 5, 6], 1.3, 1.6):
					continue
				_bush(p + o, rng.randf_range(2.0, 4.0) * (0.75 if dry else 1.0), dry)
			if not dry and w_fern > 0.0:
				var nf := int(rng.randf() * 7.0 * w_fern * (0.4 + _d_canopy(p) * 2.0))
				for i in nf:
					var o := Vector2(rng.randfn(0.0, r * 0.6), rng.randfn(0.0, r * 0.6))
					if _ok(p + o, [0, 1, 6], 1.0, 1.6):
						_fern(p + o, rng.randf_range(1.4, 2.4))
			if not dry and biome["flower"] > 0.0 and rng.randf() < 0.5:
				for i in int(rng.randf() * 3.0 * biome["flower"]):
					var o := Vector2(rng.randfn(0.0, r * 0.7), rng.randfn(0.0, r * 0.7))
					if _ok(p + o, [1, 0], 1.2, 1.4):
						_flower(p + o, rng.randf_range(0.8, 1.2))
		gx += cell


func _d_canopy(p: Vector2) -> float:
	return d._canopy_at(p)


## Wildflower meadows: their own big soft patches on grass, 10-30 m across, tens of plants each.
func _meadows() -> void:
	var w: float = biome["flower"]
	if w <= 0.0:
		return
	var cell := 18.0
	var gx := -map.half_m
	while gx < map.half_m:
		var gy := -map.half_m
		while gy < map.half_m:
			var p := Vector2(gx + rng.randf() * cell, gy + rng.randf() * cell)
			gy += cell
			var m := _meadow.get_noise_2d(p.x, p.y)
			if m < 0.22 or rng.randf() > 0.4 * w:
				continue
			if not _ok(p, [1], 2.0, 1.2, 3.0) or _d_canopy(p) > 0.25:
				continue
			if OS.get_cmdline_user_args().has("--plants-debug"):
				print("meadow %s" % p.snapped(Vector2(1, 1)))
			var r := rng.randf_range(5.0, 12.0)
			var nf := 5 + int(rng.randf() * 12.0)
			for i in nf:
				var o := Vector2(rng.randfn(0.0, r * 0.5), rng.randfn(0.0, r * 0.5))
				if _ok(p + o, [1], 2.0, 1.2, 2.0):
					_flower(p + o, rng.randf_range(0.8, 1.3))
		gx += cell


# --- forest-edge understorey ---------------------------------------------------------------------------------------

func _understorey() -> void:
	var w: float = biome["under"]
	var step := 7.0
	var gx := -map.half_m
	while gx < map.half_m:
		var gy := -map.half_m
		while gy < map.half_m:
			var p := Vector2(gx + rng.randf() * step, gy + rng.randf() * step)
			gy += step
			var cano := _d_canopy(p)
			if cano < 0.08 or cano > 0.62:
				continue
			var edge := 1.0 - absf(cano - 0.3) / 0.32   # strongest where the canopy is about to start
			if rng.randf() > edge * 0.3 * w:
				continue
			if not _ok(p, [0, 1, 6], 1.5, 1.6, 2.2):
				continue
			var dry: bool = biome["scrub"] > biome["bush"] and rng.randf() < 0.8
			var pick := rng.randf()
			if pick < 0.5 or dry:
				_bush(p, rng.randf_range(1.8, 3.2), dry)
			elif biome["fern"] > 0.0:
				for i in 1 + int(rng.randf() * 3.0):
					var o := Vector2(rng.randfn(0.0, 1.4), rng.randfn(0.0, 1.4))
					if _ok(p + o, [0, 1, 6], 1.0, 1.8, 1.4):
						_fern(p + o, rng.randf_range(1.3, 2.2))
		gx += step


# --- hedgerows -----------------------------------------------------------------------------------------------------

func _hedges(map_name: String) -> void:
	var w: float = biome["hedge"]
	var seg_noise := _noise(0.02, hash(map_name) + 5)
	var apron := d._apron
	var sdf_n := apron.get_width() if apron != null else 0
	# 1) along the paved edge, offset 4.5-6.5 m outside it (apron_sdf: byte 128 = the edge, 8 m = 127 steps)
	if apron != null:
		var step := 3.2
		var gx := -map.half_m + 4.0
		while gx < map.half_m - 4.0:
			var gy := -map.half_m + 4.0
			while gy < map.half_m - 4.0:
				var p := Vector2(gx, gy)
				gy += step
				if _n_hedge >= MAX_HEDGE:
					return
				if _gate.get_noise_2d(p.x, p.y) < 0.0 + 0.5 * (1.0 - w) or seg_noise.get_noise_2d(p.x * 1.7, p.y * 1.7) < -0.15:
					continue
				var u := (p.x + map.half_m) / (map.half_m * 2.0)
				var v := (map.half_m - p.y) / (map.half_m * 2.0)
				var px := clampi(int(u * sdf_n), 2, sdf_n - 3)
				var py := clampi(int(v * sdf_n), 2, sdf_n - 3)
				var r := apron.get_pixel(px, py).r * 255.0
				if r < 24.0 or r > 58.0:
					continue
				var gxv := apron.get_pixel(px + 2, py).r - apron.get_pixel(px - 2, py).r
				var gzv := apron.get_pixel(px, py + 2).r - apron.get_pixel(px, py - 2).r
				if absf(gxv) + absf(gzv) < 0.01:
					continue
				# the gradient points into the paving; the hedge runs along the edge. sdf rows go south, sim y north
				var grad := Vector2(gxv, -gzv).normalized()
				var along := Vector2(-grad.y, grad.x)
				var pp := p + Vector2(rng.randf_range(-0.6, 0.6), rng.randf_range(-0.6, 0.6))
				if not _ok_hedge(pp):
					continue
				_hedge_bush(pp, along)
			gx += step
	# 2) along the boundary between meadow and bare ground / dust, from a smoothed class map
	_boundary_hedges(w, seg_noise)


func _ok_hedge(p: Vector2) -> bool:
	if absf(p.x) > map.half_m - 10.0 or absf(p.y) > map.half_m - 10.0:
		return false
	if not [0, 1, 6].has(_cls(p)):
		return false
	if d._snow != null:
		var u := (p.x + map.half_m) / (map.half_m * 2.0)
		var v := (map.half_m - p.y) / (map.half_m * 2.0)
		if d._snow.get_pixel(clampi(int(u * d._snow.get_width()), 0, d._snow.get_width() - 1), clampi(int(v * d._snow.get_height()), 0, d._snow.get_height() - 1)).r > 0.25:
			return false
	var h := map.height_at(p)
	if _water > -100.0 and h < _water + 2.0:
		return false
	if absf(map.height_at(p + Vector2(3, 0)) - h) > 1.6 or absf(map.height_at(p + Vector2(0, 3)) - h) > 1.6:
		return false
	return not _near_footprint(p, 2.0) and not _near_tree(p, 2.5)


func _hedge_bush(p: Vector2, along: Vector2) -> void:
	_n_hedge += 1
	if OS.get_cmdline_user_args().has("--plants-debug") and _n_hedge % 25 == 0:
		print("hedge %s" % p.snapped(Vector2(1, 1)))
	var yaw := atan2(along.y, along.x)   # the stretched axis (local x) lies along the edge (local x = sim (cos, sin) of the yaw)
	var v := rng.randi() % 3
	var kd := _kind("hedge%d" % v, dome_mesh(11 + v * 7), RANGE_HEDGE, _mat_dome, true)
	_put3(kd, p, map.height_at(p), rng.randf_range(4.8, 5.6), rng.randf_range(2.1, 2.6), rng.randf_range(2.9, 3.5), yaw, _leaf_col(0.12), 0.12)


func _boundary_hedges(w: float, seg_noise: FastNoiseLite) -> void:
	var cell := 4.0
	var m := int(map.half_m * 2.0 / cell)
	var g := PackedFloat32Array()
	g.resize(m * m)
	var stride := maxi(1, int(round(cell / _px)))
	for r in m:
		for c in m:
			var cls := int(round(_splat.get_pixel(clampi(c * stride, 0, _n - 1), clampi(r * stride, 0, _n - 1)).r * 255.0))
			g[r * m + c] = 1.0 if cls == 1 else (0.0 if cls == 0 or cls == 5 else 0.5)
	var blur := PackedFloat32Array()
	blur.resize(m * m)
	var tmp := PackedFloat32Array()
	tmp.resize(m * m)
	var rad := 5   # box radius in cells: 44 m across
	for r in m:
		var acc := 0.0
		for c in range(-rad, rad + 1):
			acc += g[r * m + clampi(c, 0, m - 1)]
		for c in m:
			tmp[r * m + c] = acc / (2 * rad + 1)
			acc += g[r * m + clampi(c + rad + 1, 0, m - 1)] - g[r * m + clampi(c - rad, 0, m - 1)]
	for c in m:
		var acc := 0.0
		for r in range(-rad, rad + 1):
			acc += tmp[clampi(r, 0, m - 1) * m + c]
		for r in m:
			blur[r * m + c] = acc / (2 * rad + 1)
			acc += tmp[clampi(r + rad + 1, 0, m - 1) * m + c] - tmp[clampi(r - rad, 0, m - 1) * m + c]
	for r in range(2, m - 2):
		for c in range(2, m - 2):
			var b := blur[r * m + c]
			if absf(b - 0.5) > 0.035:
				continue
			if _n_hedge >= MAX_HEDGE:
				return
			var gxv := blur[r * m + c + 1] - blur[r * m + c - 1]
			var gzv := blur[(r + 1) * m + c] - blur[(r - 1) * m + c]
			if absf(gxv) + absf(gzv) < 0.05:
				continue
			var p := Vector2(-map.half_m + (c + 0.5) * cell, map.half_m - (r + 0.5) * cell)
			if _gate.get_noise_2d(p.x + 400.0, p.y) < 0.2 + 0.45 * (1.0 - w) or seg_noise.get_noise_2d(p.x * 1.3, p.y * 1.3) < -0.1:
				continue
			var grad := Vector2(gxv, -gzv).normalized()
			var along := Vector2(-grad.y, grad.x)
			var pp := p + Vector2(rng.randf_range(-1.0, 1.0), rng.randf_range(-1.0, 1.0))
			if d._no_cover_at(pp) or not _ok_hedge(pp):
				continue
			_hedge_bush(pp, along)


# --- shore ---------------------------------------------------------------------------------------------------------

func _shore(means: Array[Color]) -> int:
	var w_reed: float = biome["reed"]
	var w_peb: float = biome["pebble"]
	var n := map.vertices_per_side
	var vm := map.vertex_m
	var reed_k: Array = []
	for i in 2:
		var rk := d._kind(d._clump_mesh(2 if i == 0 else 3), 380.0)
		rk.chunk_m = 64.0
		rk.mat = _mat_reed
		rk.shadows = false
		reed_k.append(rk)
	var stone := means[2].lerp(means[4], 0.4).lerp(Color(0.42, 0.40, 0.37), 0.35)
	var pebble := d._kind(d._rock_mesh(3, 0.5), 300.0)
	var rock := d._kind(d._rock_mesh(5, 0.62), 420.0)
	var reed_noise := _noise(0.045, hash(str(map.half_m)) + 8)
	var made := 0
	var rock_n := 0
	var peb_n := 0
	for row in n - 1:
		for col in n - 1:
			if not _shore_cell(row, col):
				continue
			for s in 24:
				var p := Vector2(-map.half_m + (col + rng.randf()) * vm, map.half_m - (row + rng.randf()) * vm)
				var h := map.height_at(p)
				var above := h - _water
				if above < -0.45 or above > 1.1:
					continue
				if absf(map.height_at(p + Vector2(2.0, 0)) - h) > 0.9 or absf(map.height_at(p + Vector2(0, 2.0)) - h) > 0.9:
					continue
				if _near_footprint(p) or d._no_cover_at(p) or [2, 3].has(_cls(p)):
					continue
				var rn := reed_noise.get_noise_2d(p.x, p.y)
				if w_reed > 0.0 and above > -0.35 and above < 0.7 and rn > 0.0 and rng.randf() < 1.0 * w_reed * smoothstep(-0.05, 0.3, rn):
					for i in 1 + int(rng.randf() * 3.0):   # a clump of 1-3 cards
						var o := Vector2(rng.randfn(0.0, 0.9), rng.randfn(0.0, 0.9))
						var h2 := map.height_at(p + o)
						if h2 - _water < -0.5 or h2 - _water > 0.9:
							continue
						var tint := Color(0.40, 0.50, 0.24).lerp(Color(0.62, 0.54, 0.30), rng.randf() * 0.5) * _pg * rng.randf_range(0.8, 1.1)
						d._flat_put(reed_k[rng.randi() % 2], p + o, h2, rng.randf_range(1.5, 2.4), rng.randf_range(0.9, 1.4), rng.randf() * TAU, tint, 0.1)
						made += 1
						if made % 150 == 1 and OS.get_cmdline_user_args().has("--plants-debug"):
							print("reed %s" % (p + o).snapped(Vector2(1, 1)))
				if w_peb > 0.0 and above > -0.3 and above < 0.7 and rng.randf() < 0.5 * w_peb:
					for i in 4 + int(rng.randf() * 8.0):
						var o := Vector2(rng.randfn(0.0, 1.3), rng.randfn(0.0, 1.3))
						var h2 := map.height_at(p + o)
						if h2 - _water < -0.3 or h2 - _water > 0.8:
							continue
						d._put(pebble, p + o, h2, rng.randf_range(0.16, 0.42), stone.lightened(0.15).darkened(rng.randf_range(0.0, 0.3)), 0.2)
						peb_n += 1
					if rng.randf() < 0.3:
						d._put(rock, p, h, rng.randf_range(0.45, 1.1), stone.darkened(rng.randf_range(0.05, 0.3)), 0.15)
						rock_n += 1
	d._flat_commit("shorereed")
	d._flat.clear()
	d._commit(pebble, "shorepebble")
	d._commit(rock, "shorerock")
	counts["reed"] = made
	counts["pebble"] = peb_n
	counts["rock"] = rock_n
	return made + peb_n + rock_n


func _shore_cell(row: int, col: int) -> bool:
	var a := map.vertex_height(row, col)
	var b := map.vertex_height(row, col + 1)
	var c := map.vertex_height(row + 1, col)
	var e := map.vertex_height(row + 1, col + 1)
	return minf(minf(a, b), minf(c, e)) < _water + 1.0 and maxf(maxf(a, b), maxf(c, e)) > _water - 0.45
