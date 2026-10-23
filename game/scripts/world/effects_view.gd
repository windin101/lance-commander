class_name EffectsView
extends Node3D
## Weapon, impact, damage and destruction effects (I87), driven by SimWorld events and read-only looks at the
## sim; nothing here feeds back into the sim. Every look is data: res://data/weapon_fx.json maps a weapon's
## special_fx id (the original's Effects.csv row) to a family (beam, lightning, tracer, missile, flame, shell)
## and its tuning, and names the impacts and death sequences as lists of particle elements.
##
## Performance: one GPUParticles3D per particle kind serves the whole map (fx_particles.gdshader; emitting is
## off and emit_particle feeds it, its `amount` is the cap, emissions past it are dropped by the GPU), beams/tracers/missiles are pooled strip meshes
## (fx_beam.gdshader, per-instance uniforms, one shared material), lights and rings are pooled too. Pool sizes
## are the json's "caps"; an exhausted pool steals its oldest item (beams, lights, rings) or skips the visual
## while keeping the impact (projectiles).

const TABLE_PATH := "res://data/weapon_fx.json"
const FX_DIR := "res://assets/fx/"
const POOL_KINDS := ["ribbons", "bolts", "lights", "rings"]
## Effects draw after other transparent surfaces (the water plane sorts in front of them otherwise and hides
## splashes); they still depth-test against the opaque scene.
const RENDER_PRIORITY := 10
const FLAGS := GPUParticles3D.EMIT_FLAG_POSITION | GPUParticles3D.EMIT_FLAG_VELOCITY \
	| GPUParticles3D.EMIT_FLAG_COLOR | GPUParticles3D.EMIT_FLAG_CUSTOM

var table: Dictionary = {}
var caps: Dictionary = {}
var map: SimMap  # ground heights and the water level for misses; null in a bare scene (flat ground at y = 0)
var ground_y := 0.0  # used when map is null
var water_y := -INF  # used when map is null

var _rng := RandomNumberGenerator.new()
var _emitters: Dictionary = {}  # kind -> GPUParticles3D
var _beam_mat: ShaderMaterial
var _pools: Dictionary = {}  # "ribbons" | "bolts" | "lights" | "rings" -> Array of {node, busy, since}
var _live: Array[Dictionary] = []  # beams, bolts, projectiles, flames, burns, columns
var _timers: Array = []  # [time_left, Callable]
var _lights: Array[Dictionary] = []  # {item, t, life, energy}
var _rings: Array[Dictionary] = []  # {item, t, life, size, energy, mix}
var _tracked: Array = []  # MechViews whose damage smokes
var _damage_clock := 0.0
var _clock := 0.0
var _projectiles := 0
var _stats := {"shots": 0, "emitted": 0, "dropped_projectiles": 0, "stolen": 0}


func _init() -> void:
	_rng.seed = 87
	table = load_table()
	caps = table.get("caps", {})


func _ready() -> void:
	_beam_mat = ShaderMaterial.new()
	_beam_mat.shader = load("res://shaders/fx_beam.gdshader")
	_beam_mat.set_shader_parameter("noise_tex", _tex("noise"))
	_beam_mat.render_priority = RENDER_PRIORITY
	var emitters: Dictionary = table.get("emitters", {})
	for kind in emitters:
		if not kind.begins_with("_"):
			_emitters[kind] = _make_emitter(kind, emitters[kind], int(caps.get(kind, 512)))
	for k in POOL_KINDS:
		_pools[k] = []


func setup(sim_map: SimMap) -> void:
	map = sim_map


# --- the table ----------------------------------------------------------------------------------------------

static func load_table(path := TABLE_PATH) -> Dictionary:
	var d = JSON.parse_string(FileAccess.get_file_as_string(path))
	return d if d is Dictionary else {}


## A weapon's effective look: its family, overlaid by its special_fx entry, then by its component's entry.
static func resolve(t: Dictionary, fx_id: int, component_id := -1) -> Dictionary:
	var w: Dictionary = t.get("weapons", {}).get(str(fx_id), {})
	if w.is_empty():
		w = t.get("weapons", {}).get(str(int(t.get("forms", {}).get("Weapon", 18))), {})
	var out: Dictionary = (t.get("families", {}).get(w.get("family", ""), {}) as Dictionary).duplicate()
	for k in w:
		if k != "original":
			out[k] = w[k]
	var c: Dictionary = t.get("components", {}).get(str(component_id), {})
	for k in c:
		if not k.begins_with("_"):
			out[k] = c[k]
	out["fx_id"] = fx_id
	return out


func spec(fx_id: int, component_id := -1) -> Dictionary:
	return resolve(table, fx_id, component_id)


static func _color(v, glow := Color.WHITE) -> Color:
	if v is String:
		return glow if v == "glow" else Color.html(v)
	return Color.WHITE


static func _range(v, rng: RandomNumberGenerator) -> float:
	if v is Array:
		return rng.randf_range(float(v[0]), float(v[1]))
	return float(v) if v != null else 0.0


# --- building blocks ----------------------------------------------------------------------------------------

func _tex(name: String) -> Texture2D:
	var path := FX_DIR + name + ".png"
	return load(path) if ResourceLoader.exists(path) else null


func _make_emitter(kind: String, cfg: Dictionary, amount: int) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "fx_" + kind
	p.amount = maxi(amount, 1)
	p.lifetime = float(cfg.get("life", 2.0))
	p.local_coords = false
	p.fixed_fps = 0
	p.interpolate = false
	p.emitting = false  # emit_particle still works; nothing is auto-emitted
	p.amount_ratio = 1.0
	p.visibility_aabb = AABB(Vector3(-6000, -1000, -6000), Vector3(12000, 4000, 12000))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ShaderMaterial.new()
	pm.shader = load("res://shaders/fx_particles.gdshader")
	for k in ["gravity", "drag", "grow", "grow_power", "stretch", "spin"]:
		if cfg.has(k):
			pm.set_shader_parameter(k, float(cfg[k]))
	pm.set_shader_parameter("tumble", bool(cfg.get("tumble", false)))
	p.process_material = pm
	var shader := String(cfg.get("shader", "add"))
	var mat := ShaderMaterial.new()
	var mesh: Mesh
	if shader == "debris":
		mat.shader = load("res://shaders/fx_debris.gdshader")
		var box := BoxMesh.new()
		box.size = Vector3.ONE
		mesh = box
	else:
		mat.shader = load("res://shaders/fx_sprite_%s.gdshader" % shader)
		var q := QuadMesh.new()
		q.size = Vector2.ONE
		mesh = q
		mat.set_shader_parameter("tex", _tex(String(cfg.get("tex", "glow"))))
		mat.set_shader_parameter("cells", int(cfg.get("cells", 1)))
		mat.set_shader_parameter("streak", bool(cfg.get("streak", false)))
		for k in ["energy", "fade_in", "fade_out", "spin", "cool", "soft"]:
			if cfg.has(k):
				mat.set_shader_parameter(k, float(cfg[k]))
		if cfg.get("ramp", false):
			mat.set_shader_parameter("use_ramp", true)
			mat.set_shader_parameter("ramp", _fire_ramp())
		if shader == "mix":
			p.draw_order = GPUParticles3D.DRAW_ORDER_VIEW_DEPTH
	mat.render_priority = RENDER_PRIORITY
	mesh.surface_set_material(0, mat)
	p.draw_pass_1 = mesh
	add_child(p)
	return p


static func _fire_ramp() -> GradientTexture1D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.25, 0.5, 0.72, 0.9, 1.0])
	g.colors = PackedColorArray([Color(0.25, 0.04, 0.01), Color(0.85, 0.16, 0.02), Color(1.0, 0.42, 0.06),
		Color(1.0, 0.68, 0.22), Color(1.0, 0.9, 0.6), Color(1.0, 1.0, 0.92)])
	var t := GradientTexture1D.new()
	t.gradient = g
	t.width = 128
	return t


## One particle. size = diameter (m), life (s).
func emit(kind: String, pos: Vector3, vel: Vector3, col: Color, size: float, life: float) -> void:
	var e: GPUParticles3D = _emitters.get(kind)
	if e == null:
		return
	e.emit_particle(Transform3D(Basis(), pos), vel, col, Color(0.0, life, size, _rng.randf()), FLAGS)
	_stats["emitted"] += 1


func _strip_mesh(segments: int) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in segments:
		var y0 := float(i) / segments
		var y1 := float(i + 1) / segments
		for v in [Vector2(-1, y0), Vector2(1, y0), Vector2(1, y1), Vector2(-1, y0), Vector2(1, y1), Vector2(-1, y1)]:
			st.set_uv(Vector2((v.x + 1.0) * 0.5, v.y))
			st.add_vertex(Vector3(v.x, v.y, 0.0))
	var m := st.commit()
	m.custom_aabb = AABB(Vector3(-4, -1, -4), Vector3(8, 3, 8))
	return m


var _strip1: ArrayMesh
var _strip24: ArrayMesh


## A pooled item: a strip (ribbons, bolts), a light or a ring. Steals the oldest when the pool is full.
func _take(kind: String) -> Dictionary:
	var pool: Array = _pools[kind]
	for it in pool:
		if not it["busy"]:
			it["busy"] = true
			it["since"] = _clock
			it["node"].visible = true
			return it
	if pool.size() < int(caps.get(kind, 16)):
		var it := {"node": _new_item(kind), "busy": true, "since": _clock}
		pool.append(it)
		return it
	var oldest: Dictionary = pool[0]
	for it in pool:
		if it["since"] < oldest["since"]:
			oldest = it
	_stats["stolen"] += 1
	oldest["since"] = _clock
	oldest["gen"] = int(oldest.get("gen", 0)) + 1
	return oldest


func _new_item(kind: String) -> Node3D:
	match kind:
		"lights":
			var l := OmniLight3D.new()
			l.shadow_enabled = false
			l.omni_attenuation = 1.2
			add_child(l)
			return l
		"rings":
			var m := MeshInstance3D.new()
			var q := QuadMesh.new()
			q.size = Vector2.ONE
			m.mesh = q
			var mat := StandardMaterial3D.new()
			mat.albedo_texture = _tex("ring")
			mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			mat.cull_mode = BaseMaterial3D.CULL_DISABLED
			mat.no_depth_test = false
			mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
			mat.render_priority = RENDER_PRIORITY
			m.material_override = mat
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(m)
			return m
		_:
			if _strip1 == null:
				_strip1 = _strip_mesh(1)
				_strip24 = _strip_mesh(24)
			var m := MeshInstance3D.new()
			m.mesh = _strip24 if kind == "bolts" else _strip1
			m.material_override = _beam_mat
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			m.extra_cull_margin = 16384.0
			add_child(m)
			return m


func _release(it: Dictionary) -> void:
	it["busy"] = false
	it["node"].visible = false


## Point a strip from `a` to `b` (its Y axis spans the segment).
static func _span(node: Node3D, a: Vector3, b: Vector3) -> void:
	var axis := b - a
	if axis.length() < 0.001:
		axis = Vector3(0, 0.001, 0)
	var ref := Vector3.UP if absf(axis.normalized().y) < 0.95 else Vector3.RIGHT
	var x := axis.cross(ref).normalized()
	var z := x.cross(axis).normalized()
	node.global_transform = Transform3D(Basis(x, axis, z), a)


func _strip_params(node: GeometryInstance3D, p: Dictionary) -> void:
	for k in p:
		node.set_instance_shader_parameter(k, p[k])


# --- impacts -------------------------------------------------------------------------------------------------

## Play a named impact from the table at `at`. back: unit vector toward the shooter (sparks fly back),
## fwd: the muzzle direction (muzzle smoke), glow: the weapon's colour for "glow" entries.
func burst(name: String, at: Vector3, scale := 1.0, back := Vector3.ZERO, glow := Color.WHITE, fwd := Vector3.ZERO) -> void:
	var imp: Dictionary = table.get("impacts", {}).get(name, {})
	if imp.is_empty():
		return
	var sp := sqrt(scale)
	for el in imp.get("elements", []):
		var kind := String(el.get("emitter", "flash"))
		var n := int(round(_range(el.get("count", 1), _rng)))
		var col := _color(el.get("color", "#ffffff"), glow)
		var col2 := _color(el.get("color2"), glow) if el.has("color2") else col
		var en := float(el.get("energy", 1.0))
		var alpha := float(el.get("alpha", 1.0))
		var radius := float(el.get("radius", 0.0)) * scale
		var flat: bool = el.get("flat", false)
		for i in n:
			var c := col.lerp(col2, _rng.randf())
			c = Color(c.r * en, c.g * en, c.b * en, alpha)
			var dir := _dir(String(el.get("dir", "sphere")), float(el.get("spread", 180.0)), back, fwd)
			var off := Vector3.ZERO
			if radius > 0.0:
				off = _rand_unit() * radius * _rng.randf()
				if flat:
					off.y = absf(off.y) * 0.2
			var v := dir * _range(el.get("speed", 0.0), _rng) * sp + Vector3.UP * float(el.get("rise", 0.0)) * sp
			emit(kind, at + off, v, c, _range(el.get("size", 1.0), _rng) * scale, _range(el.get("life", 0.5), _rng))
	if imp.has("light"):
		var l: Dictionary = imp["light"]
		light(at, _color(l.get("color", "#ffa050"), glow), float(l.get("energy", 4.0)) * sp,
			float(l.get("range", 15.0)) * sp, float(l.get("life", 0.2)))
	if imp.has("ring"):
		var r: Dictionary = imp["ring"]
		ring(at, _color(r.get("color", "#ffffff"), glow), float(r.get("size", 8.0)) * scale, float(r.get("life", 0.3)),
			float(r.get("energy", 1.0)), bool(r.get("flat", false)), bool(r.get("mix", false)))


func _dir(mode: String, spread_deg: float, back: Vector3, fwd: Vector3) -> Vector3:
	var axis := Vector3.UP
	match mode:
		"sphere":
			return _rand_unit()
		"back":
			axis = back if back.length() > 0.01 else Vector3.UP
		"fwd":
			axis = fwd if fwd.length() > 0.01 else Vector3.UP
		"ground":
			var a := _rng.randf() * TAU
			return Vector3(cos(a), _rng.randf_range(0.02, 0.18), sin(a)).normalized()
	return _cone(axis.normalized(), deg_to_rad(spread_deg))


func _rand_unit() -> Vector3:
	var z := _rng.randf_range(-1.0, 1.0)
	var a := _rng.randf() * TAU
	var r := sqrt(1.0 - z * z)
	return Vector3(r * cos(a), z, r * sin(a))


func _cone(axis: Vector3, half: float) -> Vector3:
	var cos_t := lerpf(1.0, cos(half), _rng.randf())
	var sin_t := sqrt(1.0 - cos_t * cos_t)
	var a := _rng.randf() * TAU
	var ref := Vector3.UP if absf(axis.y) < 0.95 else Vector3.RIGHT
	var x := axis.cross(ref).normalized()
	var y := axis.cross(x)
	return (axis * cos_t + x * sin_t * cos(a) + y * sin_t * sin(a)).normalized()


func light(at: Vector3, col: Color, energy: float, rng: float, life: float) -> void:
	if int(caps.get("lights", 16)) <= 0:
		return
	var it := _take("lights")
	var l: OmniLight3D = it["node"]
	l.global_position = at + Vector3.UP * 1.5
	l.light_color = col
	l.omni_range = rng
	l.light_energy = energy
	for e in _lights:
		if e["item"] == it:
			_lights.erase(e)
			break
	_lights.append({"item": it, "t": 0.0, "life": maxf(life, 0.02), "energy": energy})


func ring(at: Vector3, col: Color, size: float, life: float, energy: float, flat: bool, mix: bool) -> void:
	var it := _take("rings")
	var m: MeshInstance3D = it["node"]
	var mat := m.material_override as StandardMaterial3D
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_MIX if mix else BaseMaterial3D.BLEND_MODE_ADD
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_DISABLED if flat else BaseMaterial3D.BILLBOARD_ENABLED
	var e := maxf(energy, 1.0)
	mat.albedo_color = Color(col.r * e, col.g * e, col.b * e, 0.8 if mix else 1.0)
	m.global_transform = Transform3D(Basis.from_euler(Vector3(-PI / 2.0, 0, 0)) if flat else Basis(), at + Vector3.UP * (0.4 if flat else 0.0))
	for r in _rings:
		if r["item"] == it:
			_rings.erase(r)
			break
	_rings.append({"item": it, "t": 0.0, "life": maxf(life, 0.02), "size": size, "flat": flat, "alpha": mat.albedo_color.a})


# --- ground --------------------------------------------------------------------------------------------------

func ground_height(p: Vector3) -> float:
	return map.height_at(Vector2(p.x, -p.z)) if map else ground_y


func water_height() -> float:
	return map.water_level_m if map else water_y


## Where a miss aimed at `to` from `from` lands: on the ground a few metres past or beside the target.
func miss_point(from: Vector3, to: Vector3) -> Vector3:
	var flat := Vector3(to.x - from.x, 0, to.z - from.z)
	var d := flat.normalized() if flat.length() > 0.1 else Vector3.FORWARD
	var side := d.cross(Vector3.UP)
	var p := to + d * _rng.randf_range(3.0, 14.0) + side * _rng.randf_range(-7.0, 7.0)
	p.y = maxf(ground_height(p), water_height())
	return p


func _is_water(p: Vector3) -> bool:
	return water_height() > ground_height(p) + 0.05 and absf(p.y - water_height()) < 0.5


# --- weapons -------------------------------------------------------------------------------------------------

## A weapon shot. from/to are world points (muzzle, body point); opts may carry from_node (a Node3D the muzzle
## follows), to_node + to_local (the target point in that node's frame, for held beams on a moving target),
## component (component id) and on_ground (Callable(point: Vector3, size_m: float, scorch: bool) for craters).
## Returns the visible impact point.
func fire(fx_id: int, from: Vector3, to: Vector3, hit: bool, flight: float, opts := {}) -> Vector3:
	var s := spec(fx_id, int(opts.get("component", -1)))
	_stats["shots"] += 1
	var end := to if hit else miss_point(from, to)
	var o := opts.duplicate()
	o["hit"] = hit
	if not hit:
		o.erase("to_node")
	var glow := _color(s.get("glow_color", s.get("color", "#ffffff")))
	match String(s.get("kind", "tracer")):
		"beam":
			_fire_beam(s, from, end, glow, o)
		"lightning":
			_fire_lightning(s, from, end, glow, o)
		"missile", "shell":
			var n := int(s.get("count", 1))
			for i in n:
				_after(float(s.get("stagger", 0.0)) * i, _launch.bind(s, from, end, flight, glow, o, i))
		"flame":
			_fire_flame(s, from, end, o)
		_:
			var rounds := int(s.get("rounds", 1))
			for i in rounds:
				_after(float(s.get("spacing", 0.1)) * i, _launch.bind(s, from, end, flight, glow, o, i))
	return end


## Backwards-compatible entry: a shot by weapon form only.
func spawn_shot(from: Vector3, to: Vector3, form: String, hit: bool, flight: float) -> void:
	fire(int(table.get("forms", {}).get(form, 18)), from, to, hit, flight)


## Backwards-compatible entry: a generic blast of `size` (1 = a shell hit, 3+ = an explosion).
func spawn_impact(at: Vector3, size: float = 1.0) -> void:
	if size >= 2.5:
		burst("fireball", at, size / 3.0)
	else:
		burst("ac_hit", at, maxf(size, 0.5))


func _impact(s: Dictionary, at: Vector3, from: Vector3, glow: Color, o: Dictionary, scale := 1.0) -> void:
	var back := (from - at).normalized()
	if o.get("hit", true):
		burst(String(s.get("hit", "ac_hit")), at, scale, back, glow)
		return
	var water := _is_water(at)
	burst(String(s.get("water" if water else "miss", "ac_ground")), at, scale, Vector3.UP, glow)
	if not water and o.has("on_ground"):
		var crater := float(s.get("crater", 0.0))
		var scorch := float(s.get("scorch", 0.0))
		if crater > 0.0:
			(o["on_ground"] as Callable).call(at, crater * scale, false)
		elif scorch > 0.0:
			(o["on_ground"] as Callable).call(at, scorch * scale, true)


func _muzzle(s: Dictionary, from: Vector3, to: Vector3, glow: Color) -> void:
	var m := String(s.get("muzzle", ""))
	if m != "":
		burst(m, from, 1.0, Vector3.ZERO, glow, (to - from).normalized())


func _fire_beam(s: Dictionary, from: Vector3, to: Vector3, glow: Color, o: Dictionary) -> void:
	var it := _take("ribbons")
	var dur := float(s.get("duration", 0.5))
	_strip_params(it["node"], {"core_color": _color(s.get("core_color", "#ffffff")), "glow_color": glow,
		"width": float(s.get("width", 0.5)), "core": float(s.get("core", 0.3)), "intensity": 0.0, "jitter": 0.0,
		"seed": _rng.randf(), "taper": 0.0, "shimmer": 0.35})
	_span(it["node"], from, to)
	_muzzle(s, from, to, glow)
	var local := Vector3.ZERO
	if o.has("to_node"):
		local = (o["to_node"] as Node3D).to_local(to)
	if float(s.get("light", 0.0)) > 0.0:
		light(to, glow, 3.0 * float(s["light"]), 14.0, dur)
	_live.append({"type": "beam", "item": it, "gen": int(it.get("gen", 0)), "t": 0.0, "life": dur, "spec": s, "from": from,
		"to": to, "glow": glow, "o": o, "local": local, "next_fx": 0.0, "pulse": -1})


func _fire_lightning(s: Dictionary, from: Vector3, to: Vector3, glow: Color, o: Dictionary) -> void:
	var dur := float(s.get("duration", 0.3))
	var items: Array = []
	var main := _take("bolts")
	items.append(main)
	var dist := from.distance_to(to)
	_strip_params(main["node"], {"core_color": _color(s.get("core_color", "#ffffff")), "glow_color": glow,
		"width": float(s.get("width", 0.6)), "core": float(s.get("core", 0.25)), "intensity": 1.0,
		"jitter": float(s.get("jitter", 1.4)) * clampf(dist / 120.0, 0.5, 2.5), "seed": _rng.randf(), "taper": 0.0, "shimmer": 0.0})
	_span(main["node"], from, to)
	for b in int(s.get("branches", 3)):
		var br := _take("bolts")
		items.append(br)
		_strip_params(br["node"], {"core_color": _color(s.get("core_color", "#ffffff")), "glow_color": glow,
			"width": float(s.get("width", 0.6)) * 0.5, "core": 0.22, "intensity": 0.8, "jitter": 0.9,
			"seed": _rng.randf(), "taper": 1.0, "shimmer": 0.0})
	_muzzle(s, from, to, glow)
	_impact(s, to, from, glow, o)
	_live.append({"type": "lightning", "items": items, "gens": items.map(func(i): return int(i.get("gen", 0))), "t": 0.0,
		"life": dur, "spec": s, "from": from, "to": to, "glow": glow, "next_branch": 0.0})


func _fire_flame(s: Dictionary, from: Vector3, to: Vector3, o: Dictionary) -> void:
	var dur := float(s.get("duration", 0.9))
	if float(s.get("light", 0.0)) > 0.0:
		light(from.lerp(to, 0.5), Color(1.0, 0.55, 0.2), 4.0 * float(s["light"]), 22.0, dur + 0.3)
	# the jet: a wide, flickering strip that starts thin at the nozzle (taper) under the particle stream
	var jet := _take("ribbons")
	_strip_params(jet["node"], {"core_color": _color(s.get("jet_core", "#fff0b0")), "glow_color": _color(s.get("jet_color", "#ff7a1e")),
		"width": float(s.get("jet_width", 1.6)), "core": 0.12, "intensity": 0.0, "jitter": 0.0, "seed": _rng.randf(), "taper": 1.0, "shimmer": 0.9})
	_span(jet["node"], from, to)
	_live.append({"type": "flame", "t": 0.0, "life": dur, "spec": s, "from": from, "to": to, "o": o, "acc": 0.0, "next_fx": 0.25,
		"item": jet, "gen": int(jet.get("gen", 0))})


func _launch(s: Dictionary, from: Vector3, to: Vector3, flight: float, glow: Color, o: Dictionary, index: int) -> void:
	var spread := float(s.get("spread", 0.0))
	var end := to
	if spread > 0.0:
		var j := _rand_unit() * spread * sqrt(_rng.randf())
		end += Vector3(j.x, j.y * 0.4, j.z)
		if not o.get("hit", true):
			end.y = maxf(ground_height(end), water_height())
	var start := from + _rand_unit() * (0.4 if s.get("kind") == "missile" else 0.0)
	if index == 0 or s.get("kind") != "tracer":
		_muzzle(s, start, end, glow)
	var life := maxf(flight, 0.06) + (_rng.randf_range(-0.08, 0.12) if s.get("kind") == "missile" else 0.0)
	if _projectiles >= int(caps.get("projectiles", 320)):
		_stats["dropped_projectiles"] += 1
		_after(life, _impact.bind(s, end, from, glow, o))
		return
	_projectiles += 1
	var it := _take("ribbons")
	var kind := String(s.get("kind", "tracer"))
	var core := _color(s.get("core_color", "#ffffff"))
	var col := _color(s.get("color", "#ffd23a"))
	_strip_params(it["node"], {"core_color": core, "glow_color": col, "width": float(s.get("width", 0.35)),
		"core": float(s.get("core", 0.45)), "intensity": 1.0, "jitter": 0.0, "seed": _rng.randf(), "taper": 1.0, "shimmer": 0.0})
	var dist := start.distance_to(end)
	var arc := 0.0
	if kind in ["missile", "shell"]:
		arc = float(s.get("arc", 0.0)) + float(s.get("arc_per_m", 0.0)) * dist
	var p := {"type": "proj", "item": it, "gen": int(it.get("gen", 0)), "t": 0.0, "life": life, "spec": s, "from": start,
		"to": end, "arc": arc, "glow": col, "o": o, "acc": 0.0, "prev": start, "wobble": _rng.randf() * TAU,
		"shock": float(s.get("shock", 0.0)) > 0.0}
	if p["shock"]:
		var tr := _take("ribbons")
		_strip_params(tr["node"], {"core_color": Color(0.85, 0.9, 1.0), "glow_color": Color(0.35, 0.45, 0.6),
			"width": float(s.get("width", 0.4)) * 0.9, "core": 0.12, "intensity": 0.55, "jitter": 0.0, "seed": 0.0,
			"taper": 1.0, "shimmer": 0.6})
		p["trail"] = tr
		p["trail_gen"] = int(tr.get("gen", 0))
	_live.append(p)


func _path(p: Dictionary, k: float) -> Vector3:
	var pos: Vector3 = (p["from"] as Vector3).lerp(p["to"], k)
	var arc: float = p["arc"]
	if arc > 0.0:
		pos.y += 4.0 * arc * k * (1.0 - k)
		if p["spec"].get("kind") == "missile":
			var d: Vector3 = (p["to"] - p["from"])
			var side := d.cross(Vector3.UP).normalized()
			pos += side * sin(k * PI) * sin(p["wobble"]) * arc * 0.25
	return pos


func _after(t: float, f: Callable) -> void:
	if t <= 0.0:
		f.call()
	else:
		_timers.append([t, f])


# --- damage and destruction ----------------------------------------------------------------------------------

## Damaged units smoke (and spark and burn when critical) from their smoke nodes and destroyed locations.
func track(view: Node3D) -> void:
	if not _tracked.has(view):
		_tracked.append(view)


## A unit or building is destroyed: the table's death sequence at `at` (its base), scaled by `size`
## (1 = a 10 m mech), then a lingering smoke column and flames at the base.
func destroyed(kind: String, at: Vector3, size := 1.0, height := 10.0) -> void:
	var d: Dictionary = table.get("deaths", {}).get(kind, {})
	if d.is_empty():
		return
	for step in d.get("sequence", []):
		var p := at + Vector3.UP * height * float(step[2])
		_after(float(step[0]), burst.bind(String(step[1]), p, size, Vector3.UP, Color.WHITE, Vector3.ZERO))
	var col: Dictionary = d.get("column", {})
	if not col.is_empty():
		var n := 0
		for e in _live:
			if e["type"] == "column":
				n += 1
		if n >= int(caps.get("columns", 24)):
			for e in _live:
				if e["type"] == "column":
					_live.erase(e)
					break
		_live.append({"type": "column", "t": 0.0, "life": float(col.get("life", 40.0)), "rate": float(col.get("rate", 4.0)),
			"size": float(col.get("size", 4.0)) * size, "at": at + Vector3.UP * height * 0.3, "acc": 0.0,
			"burn": float(d.get("burn", 0.0)), "spread": height * 0.25 * size,
			"wind": Vector3(float(col.get("wind", [0, 0])[0]), 0.0, float(col.get("wind", [0, 0])[1]))})


func live_count() -> int:
	var n := _live.size()
	for l in _lights:
		n += 1
	return n


func stats() -> Dictionary:
	var s := _stats.duplicate()
	s["live"] = _live.size()
	s["projectiles"] = _projectiles
	for k in POOL_KINDS:
		s["pool_" + k] = _pools.get(k, []).size()
	s["tracked"] = _tracked.size()
	return s


# --- per frame -----------------------------------------------------------------------------------------------

var _warm := 0  # frames of prewarm left; see _prewarm


## Draw every particle kind, a beam, a bolt, a light and a ring once, invisibly, in front of the camera on the
## first frames, so their pipelines compile while the mission loads and not at the first shot (a 2.7 s hitch).
func _prewarm(cam: Camera3D) -> void:
	var p := cam.global_position - cam.global_transform.basis.z * 40.0
	for kind in _emitters:
		emit(kind, p, Vector3.ZERO, Color(0, 0, 0, 0), 0.01, 0.2)
	for k in ["ribbons", "bolts"]:
		var it := _take(k)
		_strip_params(it["node"], {"intensity": 0.0})
		_span(it["node"], p, p + Vector3.RIGHT)
		_after(0.25, _release.bind(it))
	light(p, Color.BLACK, 0.0, 1.0, 0.2)
	ring(p, Color(0, 0, 0, 0), 0.01, 0.2, 0.0, true, true)
	_stats["emitted"] -= _emitters.size()


func _process(delta: float) -> void:
	_clock += delta
	if _warm < 2:
		var cam := get_viewport().get_camera_3d()
		if cam:
			_warm += 1
			if _warm == 1:
				_prewarm(cam)
	if not _timers.is_empty():
		var due: Array = []
		var keep: Array = []
		for t in _timers:
			t[0] -= delta
			if t[0] <= 0.0:
				due.append(t[1])
			else:
				keep.append(t)
		_timers = keep
		for f in due:
			(f as Callable).call()
	var still: Array[Dictionary] = []
	for e in _live:
		e["t"] += delta
		var alive := true
		match e["type"]:
			"beam":
				alive = _tick_beam(e, delta)
			"lightning":
				alive = _tick_lightning(e, delta)
			"proj":
				alive = _tick_proj(e, delta)
			"flame":
				alive = _tick_flame(e, delta)
			"burn":
				alive = _tick_burn(e, delta)
			"column":
				alive = _tick_column(e, delta)
		if alive:
			still.append(e)
	_live = still
	_tick_lights(delta)
	_tick_rings(delta)
	_damage_clock += delta
	if _damage_clock >= 0.1:
		_tick_damage(_damage_clock)
		_damage_clock = 0.0


func _owns(e: Dictionary, key := "item", gen_key := "gen") -> bool:
	var it: Dictionary = e[key]
	return int(it.get("gen", 0)) == int(e[gen_key]) and it["busy"]


func _tick_beam(e: Dictionary, delta: float) -> bool:
	if not _owns(e):
		return false
	var s: Dictionary = e["spec"]
	var node: GeometryInstance3D = e["item"]["node"]
	var t: float = e["t"]
	var life: float = e["life"]
	var o: Dictionary = e["o"]
	var from: Vector3 = e["from"]
	if o.has("from_node") and is_instance_valid(o["from_node"]):
		from = (o["from_node"] as Node3D).global_position
	var to: Vector3 = e["to"]
	if o.has("to_node") and is_instance_valid(o["to_node"]):
		to = (o["to_node"] as Node3D).to_global(e["local"])
	var wig := Vector3(_rng.randf_range(-0.15, 0.15), _rng.randf_range(-0.15, 0.15), _rng.randf_range(-0.15, 0.15))
	_span(node, from, to + wig)
	var env := clampf(t / 0.035, 0.0, 1.0) * clampf((life - t) / 0.1, 0.0, 1.0)
	var on := true
	var pulses := int(s.get("pulses", 0))
	if pulses > 0:
		var period := life / pulses
		var phase := fmod(t, period) / period
		on = phase < float(s.get("pulse_on", 0.5))
		var k := int(t / period)
		if on and k != e["pulse"]:
			e["pulse"] = k
			if k > 0:
				_muzzle(s, from, to, e["glow"])
		env *= clampf(phase / 0.08, 0.0, 1.0) if on else 0.0
	var flick := 1.0 - float(s.get("flicker", 0.1)) * _rng.randf()
	node.set_instance_shader_parameter("intensity", env * flick)
	e["next_fx"] -= delta
	if on and e["next_fx"] <= 0.0 and t < life - 0.05:
		_impact(s, to, from, e["glow"], o if t < 0.05 else _no_decal(o))
		var imp: Dictionary = table.get("impacts", {}).get(String(s.get("hit" if o.get("hit", true) else "miss", "")), {})
		e["next_fx"] = float(imp.get("repeat", 0.1))
	if t >= life:
		_release(e["item"])
		return false
	return true


static func _no_decal(o: Dictionary) -> Dictionary:
	var c := o.duplicate()
	c.erase("on_ground")
	return c


func _tick_lightning(e: Dictionary, delta: float) -> bool:
	var items: Array = e["items"]
	var gens: Array = e["gens"]
	var t: float = e["t"]
	var life: float = e["life"]
	var from: Vector3 = e["from"]
	var to: Vector3 = e["to"]
	var env := clampf((life - t) / 0.12, 0.0, 1.0)
	e["next_branch"] -= delta
	var rebranch: bool = e["next_branch"] <= 0.0
	if rebranch:
		e["next_branch"] = 0.07
	var axis := to - from
	for i in items.size():
		var it: Dictionary = items[i]
		if int(it.get("gen", 0)) != int(gens[i]) or not it["busy"]:
			continue
		var node: GeometryInstance3D = it["node"]
		node.set_instance_shader_parameter("intensity", env * _rng.randf_range(0.55, 1.0) * (1.0 if i == 0 else 0.8))
		if i == 0:
			if rebranch:
				node.set_instance_shader_parameter("seed", _rng.randf())
			continue
		if rebranch:
			var a := from + axis * _rng.randf_range(0.15, 0.85)
			var side := axis.cross(Vector3.UP).normalized()
			if side.length() < 0.1:
				side = Vector3.RIGHT
			var b := a + (side * _rng.randf_range(-1.0, 1.0) + Vector3.UP * _rng.randf_range(-0.6, 0.9)).normalized() \
				* _rng.randf_range(5.0, 14.0) + axis.normalized() * _rng.randf_range(0.0, 8.0)
			_span(node, b, a)  # tail at the tip: the taper narrows it to nothing there
			node.set_instance_shader_parameter("seed", _rng.randf())
	if t >= life:
		for i in items.size():
			if int(items[i].get("gen", 0)) == int(gens[i]):
				_release(items[i])
		return false
	return true


func _tick_proj(e: Dictionary, delta: float) -> bool:
	var s: Dictionary = e["spec"]
	var k := clampf(e["t"] / e["life"], 0.0, 1.0)
	var pos := _path(e, k)
	var prev: Vector3 = e["prev"]
	var owned := _owns(e)
	if owned:
		var len := float(s.get("length", 4.0))
		var dir := (pos - prev).normalized() if pos.distance_to(prev) > 0.001 else ((e["to"] as Vector3) - (e["from"] as Vector3)).normalized()
		var tail := pos - dir * minf(len, pos.distance_to(e["from"]) + 0.01)
		_span(e["item"]["node"], tail, pos)
	if e.has("trail") and int(e["trail"].get("gen", 0)) == int(e["trail_gen"]):
		var tail2: Vector3 = (e["from"] as Vector3).lerp(pos, clampf(1.0 - 120.0 / maxf(pos.distance_to(e["from"]), 1.0), 0.0, 1.0))
		_span(e["trail"]["node"], tail2, pos)
	var rate := float(s.get("smoke_rate", 0.0))
	if rate > 0.0:
		e["acc"] += delta * rate
		var smoke := _color(s.get("smoke", "#c8c4bc"))
		var steps := int(e["acc"])
		for i in steps:
			var q := prev.lerp(pos, (i + 1.0) / steps)
			emit("smoke", q + _rand_unit() * 0.3, _rand_unit() * 0.8, Color(smoke.r, smoke.g, smoke.b, 0.42),
				float(s.get("smoke_size", 1.4)) * _rng.randf_range(0.7, 1.1), float(s.get("smoke_life", 2.0)) * _rng.randf_range(0.7, 1.1))
		e["acc"] -= steps
		if _rng.randf() < 0.6:
			var g: Color = e["glow"]
			emit("flash", pos, Vector3.ZERO, Color(g.r * 3.0, g.g * 3.0, g.b * 3.0, 1.0), float(s.get("width", 0.3)) * 5.0, 0.05)
	e["prev"] = pos
	if k >= 1.0:
		_projectiles -= 1
		if owned:
			_release(e["item"])
		if e.has("trail") and int(e["trail"].get("gen", 0)) == int(e["trail_gen"]):
			_release(e["trail"])
		_impact(s, e["to"], e["from"], e["glow"], e["o"], 1.0)
		return false
	return true


func _tick_flame(e: Dictionary, delta: float) -> bool:
	var s: Dictionary = e["spec"]
	var o: Dictionary = e["o"]
	var from: Vector3 = e["from"]
	if o.has("from_node") and is_instance_valid(o["from_node"]):
		from = (o["from_node"] as Node3D).global_position
	var to: Vector3 = e["to"]
	var d := to - from
	var dist := d.length()
	var dir := d / maxf(dist, 0.01)
	var travel := 0.45
	e["acc"] += delta * float(s.get("rate", 70.0))
	var n := int(e["acc"])
	e["acc"] -= n
	var w := float(s.get("width", 2.6))
	for i in n:
		var v := _cone(dir, deg_to_rad(5.0)) * dist / travel * _rng.randf_range(0.85, 1.1)
		var start := from + d * _rng.randf_range(0.0, 0.25)
		emit("flame", start, v, Color(1, 1, 1, 1), w * _rng.randf_range(0.35, 0.65), travel * _rng.randf_range(0.9, 1.25))
	if _owns(e):
		var env := clampf(e["t"] / 0.08, 0.0, 1.0) * clampf((e["life"] - e["t"]) / 0.15, 0.0, 1.0)
		_span(e["item"]["node"], from, to)
		(e["item"]["node"] as GeometryInstance3D).set_instance_shader_parameter("intensity", env * _rng.randf_range(0.3, 0.5))
	e["next_fx"] -= delta
	if e["next_fx"] <= 0.0:
		e["next_fx"] = 0.1
		_impact(s, to, from, Color.WHITE, o if e["t"] < 0.4 else _no_decal(o))
	if e["t"] >= e["life"]:
		if _owns(e):
			_release(e["item"])
		var burn := float(s.get("burn", 0.0))
		if burn > 0.0 and not _is_water(to):
			var at := to
			if not o.get("hit", true):
				at.y = ground_height(to)
			_live.append({"type": "burn", "t": 0.0, "life": burn, "at": at, "next_fx": 0.0})
		return false
	return true


func _tick_burn(e: Dictionary, delta: float) -> bool:
	e["next_fx"] -= delta
	if e["next_fx"] <= 0.0:
		var fade: float = 1.0 - e["t"] / e["life"]
		e["next_fx"] = 0.12 / maxf(fade, 0.25)
		burst("burning_ground", e["at"], 0.6 + 0.4 * fade)
	return e["t"] < e["life"]


func _tick_column(e: Dictionary, delta: float) -> bool:
	var k: float = e["t"] / e["life"]
	var rate: float = e["rate"] * (1.0 - k) * (1.0 - k) + 0.4
	e["acc"] += delta * rate
	var size: float = e["size"]
	var at: Vector3 = e["at"]
	while e["acc"] >= 1.0:
		e["acc"] -= 1.0
		var off: Vector3 = Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)) * e["spread"]
		var wind: Vector3 = e["wind"]
		emit("smoke", at + off, wind + Vector3(_rng.randf_range(-0.6, 0.6), _rng.randf_range(5.0, 8.5), _rng.randf_range(-0.6, 0.6)),
			Color(0.16, 0.15, 0.14, 0.65), size * _rng.randf_range(0.8, 1.2), _rng.randf_range(8.0, 12.0))
	if e["t"] < e["burn"]:
		var f: float = 1.0 - e["t"] / e["burn"]
		if _rng.randf() < delta * 14.0 * f:
			var off: Vector3 = Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)) * e["spread"]
			emit("fire", at + off, Vector3(0, _rng.randf_range(1.5, 3.5), 0), Color(1, 1, 1, 1), size * _rng.randf_range(0.35, 0.6), _rng.randf_range(0.5, 0.9))
	return e["t"] < e["life"]


func _tick_lights(delta: float) -> void:
	var keep: Array[Dictionary] = []
	for l in _lights:
		l["t"] += delta
		var k: float = l["t"] / l["life"]
		var it: Dictionary = l["item"]
		if k >= 1.0:
			_release(it)
			continue
		(it["node"] as OmniLight3D).light_energy = l["energy"] * (1.0 - k) * (1.0 - k)
		keep.append(l)
	_lights = keep


func _tick_rings(delta: float) -> void:
	var keep: Array[Dictionary] = []
	for r in _rings:
		r["t"] += delta
		var k: float = r["t"] / r["life"]
		var it: Dictionary = r["item"]
		if k >= 1.0:
			_release(it)
			continue
		var m: MeshInstance3D = it["node"]
		var s: float = r["size"] * (0.25 + 0.75 * sqrt(k))
		var b := m.global_transform.basis.orthonormalized()
		m.global_transform = Transform3D(b.scaled(Vector3.ONE * s), m.global_transform.origin)
		var mat := m.material_override as StandardMaterial3D
		mat.albedo_color.a = r["alpha"] * (1.0 - k)
		keep.append(r)
	_rings = keep


func _tick_damage(dt: float) -> void:
	var cfg: Dictionary = table.get("damage", {})
	var cam := get_viewport().get_camera_3d() if is_inside_tree() else null
	var cands: Array = []
	var keep: Array = []
	for v in _tracked:
		if not is_instance_valid(v):
			continue
		keep.append(v)
		if not v.has_method("damage_fraction") or v.get("_wrecked") or not v.visible:
			continue
		var f: float = v.damage_fraction()
		if f >= float(cfg.get("smoke_from", 0.3)) or (v.has_method("destroyed_locations") and not v.destroyed_locations().is_empty()):
			cands.append([cam.global_position.distance_squared_to(v.global_position) if cam else 0.0, v, f])
	_tracked = keep
	cands.sort_custom(func(a, b): return a[0] < b[0])
	var smoke := _color(cfg.get("smoke_color", "#3a3836"))
	var wv: Array = cfg.get("wind", [0.0, 0.0])
	var wind := Vector3(float(wv[0]), 0.0, float(wv[1]))
	for i in mini(cands.size(), int(caps.get("damage_smokers", 48))):
		var v: Node3D = cands[i][1]
		var f: float = cands[i][2]
		var from := float(cfg.get("smoke_from", 0.3))
		var k := clampf((f - from) / maxf(1.0 - from, 0.01), 0.0, 1.0)
		var rate := float(cfg.get("smoke_rate", 5.0)) * (0.25 + 0.75 * k) if f >= from else 0.0
		var size: float = float(cfg.get("smoke_size", 2.2)) * float(v.call("fx_scale"))
		if _rng.randf() < rate * dt:
			emit("smoke", v.call("smoke_point"), wind + Vector3(_rng.randf_range(-0.4, 0.4), _rng.randf_range(2.0, 3.5), _rng.randf_range(-0.4, 0.4)),
				Color(smoke.r, smoke.g, smoke.b, 0.6 + 0.3 * k), size * (0.8 + 0.6 * k), _rng.randf_range(4.0, 6.5))
		for loc in v.call("destroyed_locations"):
			if _rng.randf() < float(cfg.get("limb_rate", 2.0)) * dt:
				emit("smoke", v.call("body_point", loc), Vector3(0, _rng.randf_range(1.0, 2.5), 0), Color(smoke.r, smoke.g, smoke.b, 0.55),
					size * 0.8, _rng.randf_range(2.5, 4.0))
		if f >= float(cfg.get("critical", 0.65)):
			if _rng.randf() < float(cfg.get("spark_rate", 2.5)) * dt:
				var p: Vector3 = v.call("body_point", _rng.randi_range(1, 5))
				for j in 5:
					emit("spark", p, _rand_unit() * _rng.randf_range(6.0, 14.0) + Vector3.UP * 3.0, Color(4.0, 3.0, 1.6, 1.0), 0.14, _rng.randf_range(0.3, 0.6))
				emit("flash", p, Vector3.ZERO, Color(3.0, 2.4, 1.4, 1.0), 1.2, 0.08)
			if _rng.randf() < float(cfg.get("fire_rate", 5.0)) * dt:
				emit("fire", v.call("smoke_point"), Vector3(0, _rng.randf_range(1.0, 2.5), 0), Color(1, 1, 1, 1),
					size * _rng.randf_range(0.6, 0.9), _rng.randf_range(0.4, 0.7))
