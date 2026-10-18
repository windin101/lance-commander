class_name MechView
extends Node3D
## Visual for one moving unit (mech or ground vehicle): model (team-painted for
## mechs), gesture animation from the sim body state, interpolation between sim
## ticks, wreck swap when disabled. Hovercraft ride the water surface.
## Model forward is +Z; sim facing f (0 = north, clockwise) -> rotation.y = PI - f.

const LOOPED := ["Idle", "Walk", "Run", "LimpLeft", "LimpRight"]

var mech: SimUnit
var map: SimMap
var model: Node3D
var player: AnimationPlayer
var sidecar: Dictionary = {}
var weapon_nodes: Array[Node3D] = []
var ring: MeshInstance3D
var selected := false: set = set_selected
var _anim := ""
var _wrecked := false
var _next_weapon := 0


func setup(sim_mech: SimUnit, sim_map: SimMap) -> void:
	mech = sim_mech
	map = sim_map
	name = "Unit%d_%s" % [mech.id, mech.model]
	var path := _asset_path(".glb")
	if not ResourceLoader.exists(path):
		push_warning("no model for %s" % mech.model)
		model = Node3D.new()
	else:
		model = load(path).instantiate()
	add_child(model)
	_paint(model)
	player = model.find_child("AnimationPlayer", true, false)
	if player:
		for a in LOOPED:
			if player.has_animation(a):
				player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	var side_path := "res://assets/mechs/%s.json" % mech.model
	if mech is SimMech and FileAccess.file_exists(side_path):
		sidecar = JSON.parse_string(FileAccess.get_file_as_string(side_path))
		for w in sidecar.get("weapon_nodes", []):
			var n := model.find_child(w["node"], true, false) as Node3D
			if n:
				weapon_nodes.append(n)
	ring = MeshInstance3D.new()
	var torus := TorusMesh.new()
	var radius := 5.5 if mech is SimMech else (1.6 if mech.tonnage < 5 else 3.6)
	torus.inner_radius = radius - 0.3
	torus.outer_radius = radius + 0.3
	torus.rings = 48
	ring.mesh = torus
	var rm := StandardMaterial3D.new()
	rm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	rm.albedo_color = Color(0.3, 1.0, 0.4) if mech.is_player else Color(1.0, 0.3, 0.25)
	rm.no_depth_test = true
	ring.material_override = rm
	ring.visible = false
	add_child(ring)
	sync(1.0)


func _asset_path(suffix: String) -> String:
	var folder := "mechs" if mech is SimMech else "vehicles"
	return "res://assets/%s/%s%s" % [folder, mech.model, suffix]


func _paint(root: Node) -> void:
	if mech.paint.size() == 3:
		MechPaint.apply(root, mech.model, MechPaint.argb(mech.paint[0]), MechPaint.argb(mech.paint[1]),
			MechPaint.argb(mech.paint[2]), "mechs" if mech is SimMech else "vehicles")


func set_selected(v: bool) -> void:
	selected = v
	if ring:
		ring.visible = v and not _wrecked


## Place and animate for interpolation factor alpha (0 = previous tick, 1 = current).
func sync(alpha: float) -> void:
	var pos := mech.prev_position.lerp(mech.position, alpha)
	var facing := rad_to_deg(lerp_angle(deg_to_rad(mech.prev_facing), deg_to_rad(mech.facing), alpha))
	var ground := map.height_at(pos)
	if mech.hover:
		ground = maxf(ground, map.water_level_m)
	position = TerrainView.to_3d(pos, ground)
	rotation.y = PI - deg_to_rad(facing)
	if mech.is_disabled():
		_wreck()
		return
	_animate()


func _animate() -> void:
	if player == null:
		return
	if not (mech is SimMech) and not (player.has_animation("Walk") or player.has_animation("Run")):
		return
	var want := "Idle" if player.has_animation("Idle") else ""
	if not (mech is SimMech):
		# Vehicles: only infantry carry Walk/Run; otherwise hold still.
		want = "Run" if mech.speed > mech.walk_speed + 0.5 else ("Walk" if mech.speed > 0.1 else "")
	var scale := 1.0
	match mech.body_state:
		SimMech.BodyState.WALKING:
			want = "Walk"
			scale = clampf(mech.speed / maxf(mech.walk_speed, 0.1), 0.4, 1.6)
		SimMech.BodyState.RUNNING:
			want = "Run"
			scale = clampf(mech.speed / maxf(mech.run_speed, 0.1), 0.5, 1.4)
		SimMech.BodyState.LIMPING:
			var left_gone: bool = mech is SimMech and mech.damage_state[SimMech.Body.LLEG] == SimMech.DamageState.DESTROYED
			want = "LimpLeft" if left_gone else "LimpRight"
		SimMech.BodyState.FALLEN_FORWARD, SimMech.BodyState.FALLEN_BACKWARD:
			want = "FallForward"
	if want == "Idle" and _anim == "FallForward":
		want = "GetUpFront"
	if _anim == "GetUpFront" and player.is_playing():
		return
	if want == "":
		if player.is_playing():
			player.stop()
		_anim = ""
		return
	if want != _anim and player.has_animation(want):
		player.play(want, 0.2)
		_anim = want
	player.speed_scale = scale


func _wreck() -> void:
	if _wrecked:
		return
	_wrecked = true
	ring.visible = false
	var path := _asset_path("_wreck_forward.glb" if mech is SimMech else "_wreck.glb")
	if ResourceLoader.exists(path):
		model.queue_free()
		model = load(path).instantiate()
		add_child(model)
		_paint(model)
		player = null


## World-space muzzle point for the next shot, cycling the model's weapon nodes.
func muzzle() -> Vector3:
	if weapon_nodes.is_empty() or _wrecked:
		return global_position + Vector3.UP * 6.0
	var n := weapon_nodes[_next_weapon % weapon_nodes.size()]
	_next_weapon += 1
	return n.global_position


## A point on the body to aim at, for effects.
func aim_point() -> Vector3:
	var h := 5.0 if mech is SimMech else (0.9 if mech.tonnage < 5 else 2.0)
	return global_position + Vector3.UP * h
