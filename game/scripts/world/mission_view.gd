extends Node3D
## A playable mission: terrain, map objects, mechs, effects, RTS commands.
## The SimWorld steps at a fixed 10 Hz; views interpolate between ticks.
## Dev args: --demo (player lance attacks the nearest enemy), --arena (moves the
## Starslayer onto open ground 110 m north of the lance first), --sim-seconds=N
## (fast-forward before the first frame), --focus=player|battle.

@export var mission := "mc2_01"

var sm: SimMission
var world: SimWorld
var terrain: TerrainView
var objects_view: ObjectsView
var effects: EffectsView
var input: CommandInput
var camera: RtsCamera
var views: Dictionary = {}  # mech id -> MechView
var hud: MissionHud
var audio: AudioDirector
var sequencer: MissionSequencer
var _voice_cfg: Array = []
var _voice_flags_done := {}
var _acc := 0.0
var _args := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	sm = SimMission.load_mission(GameData, mission)
	world = sm.world
	var mission_fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % mission))
	var cam_block: Dictionary = mission_fit.get("Cameras", {})

	terrain = TerrainView.new()
	terrain.name = "Terrain"
	add_child(terrain)
	terrain.build(world.map, "res://assets/maps/%s" % mission)
	objects_view = ObjectsView.new()
	objects_view.name = "Objects"
	add_child(objects_view)
	objects_view.build(world.map, mission)
	_lighting(cam_block)

	for m in world.units:
		if not m.is_mover():
			continue
		var v := MechView.new()
		add_child(v)
		v.setup(m, world.map)
		views[m.id] = v
	effects = EffectsView.new()
	effects.name = "Effects"
	add_child(effects)

	camera = RtsCamera.new()
	camera.name = "Camera"
	camera.far = 6000.0
	camera.bounds_half = world.map.half_m
	camera.height_at = world.map.height_at
	camera.yaw_deg = float(cam_block.get("StartRotation", 0.0))
	camera.distance = 220.0
	add_child(camera)
	camera.make_current()
	_focus_player()

	input = CommandInput.new()
	input.world = world
	input.views = views
	input.camera = camera
	input.player_team = sm.player_team
	add_child(input)
	_build_hud()
	audio = AudioDirector.new()
	audio.name = "Audio"
	add_child(audio)
	var bcfg_path := "res://data/brains/%s.json" % mission
	var script_cfg: Dictionary = {}
	if FileAccess.file_exists(bcfg_path):
		script_cfg = JSON.parse_string(FileAccess.get_file_as_string(bcfg_path)).get("script", {})
	_voice_cfg = script_cfg.get("voice", [])
	sequencer = MissionSequencer.new()
	sequencer.name = "Sequencer"
	add_child(sequencer)
	sequencer.setup(self, script_cfg)
	for v in views.values():
		v.footstep.connect(func(at: Vector3): audio.sfx("footstep", at, -10.0))

	if _args.has("arena"):
		_arena()
	if _args.has("demo"):
		_demo_orders()
	var ff := float(_args.get("sim-seconds", "0"))
	while ff > 0.0:
		sm.step()
		_consume_events(false)
		ff -= SimWorld.TICK
	if _args.get("focus", "") == "battle":
		_focus_battle()
	if _args.has("select-all"):
		input._set_selection(world.units.filter(func(u): return u.team == sm.player_team and u.is_mover() and not u.is_disabled()))
	for v in views.values():
		v.sync(1.0)


func _process(delta: float) -> void:
	_acc += delta
	while _acc >= SimWorld.TICK:
		sm.step()
		_acc -= SimWorld.TICK
	var alpha := _acc / SimWorld.TICK
	for v in views.values():
		v.sync(alpha)
	_consume_events(true)
	if audio:
		for v in _voice_cfg:
			if v.has("flag") and world.flags.get(v["flag"], false) and not _voice_flags_done.has(v["flag"]):
				_voice_flags_done[v["flag"]] = true
				audio.say_later(v["vo"], float(v.get("delay", 0.0)), world.time)
		audio.tick(world.time)
		audio.update_music(sm.objectives.result, world.time)


func _consume_events(show: bool) -> void:
	for e in world.events:
		if not show:
			continue
		if hud:
			hud.on_event(e)
		if audio:
			_audio_event(e)
		match e["type"]:
			"shot":
				if not (views.has(e["from"]) and views.has(e["to"])):
					continue
				var from: MechView = views[e["from"]]
				var to: MechView = views[e["to"]]
				effects.spawn_shot(from.muzzle(), to.aim_point(), e["form"], e["hit"], e["flight"])
			"impact":
				if e.get("damage", 0.0) >= 5.0 and views.has(e["unit"]):
					effects.spawn_impact(views[e["unit"]].aim_point(), 0.7)
			"disabled":
				var u: SimUnit = world.units[e["unit"]]
				if u is SimStructure:
					objects_view.destroy(u.object_index)
					effects.spawn_impact(TerrainView.to_3d(u.position, world.map.height_at(u.position) + 6.0), 4.0)
				elif views.has(e["unit"]):
					effects.spawn_impact(views[e["unit"]].aim_point(), 3.0)
	world.events.clear()


func _audio_event(e: Dictionary) -> void:
	match e["type"]:
		"shot":
			if views.has(e["from"]):
				var shooter: SimUnit = world.units[e["from"]]
				audio.weapon_fire(int(shooter.items[e["weapon"]]["master_id"]), views[e["from"]].global_position)
				if shooter.team == sm.player_team or world.units[e["to"]].team == sm.player_team:
					audio.last_combat_time = world.time
		"impact":
			var u: SimUnit = world.units[e["unit"]]
			var at := TerrainView.to_3d(u.position, world.map.height_at(u.position) + 4.0)
			audio.hit(String(e.get("form", "")), float(e.get("damage", 0.0)), at)
		"disabled":
			var u: SimUnit = world.units[e["unit"]]
			var at := TerrainView.to_3d(u.position, world.map.height_at(u.position) + 4.0)
			var key := "mech_explode" if u is SimMech else ("building_explode" if u is SimStructure else "vehicle_explode")
			audio.sfx(key, at, 2.0)
		"fell":
			var u: SimUnit = world.units[e["unit"]]
			audio.sfx("fall", TerrainView.to_3d(u.position, world.map.height_at(u.position)), 0.0)
		"objective":
			if not e["hidden"]:
				audio.announce("objective_done")
			if sequencer:
				sequencer.on_objective(int(e["index"]))
			for v in _voice_cfg:
				if v.has("objective") and int(v["objective"]) == int(e["index"]):
					audio.say_later(v["vo"], float(v.get("delay", 0.0)), world.time)
		"mission_end":
			audio.announce("win" if e["won"] else "lose")


func _demo_orders() -> void:
	for m in world.units:
		if m.team != sm.player_team:
			continue
		var best: SimUnit = null
		for e in world.enemies_of(m):
			if best == null or m.distance_to(e.position) < m.distance_to(best.position):
				best = e
		if best:
			world.order_attack(m, best)


func _arena() -> void:
	var c := Vector2.ZERO
	var n := 0
	for m in world.units:
		if m.team == sm.player_team:
			c += m.position
			n += 1
	c /= maxf(n, 1)
	for m in world.units:
		if m.name == "Starslayer":
			m.position = world.map.nearest_walkable(c + Vector2(0, 110))
			m.prev_position = m.position
			m.facing = 180.0
			m.prev_facing = 180.0


func _focus_player() -> void:
	var c := Vector2.ZERO
	var n := 0
	for m in world.units:
		if m.team == sm.player_team:
			c += m.position
			n += 1
	if n > 0:
		c /= n
		camera.focus = Vector3(c.x, 0, -c.y)


func _focus_battle() -> void:
	for m in world.units:
		if m.team == sm.player_team and m.current_target:
			var mid := (m.position + m.current_target.position) / 2.0
			camera.focus = Vector3(mid.x, 0, -mid.y)
			return
	_focus_player()


func _lighting(cam_block: Dictionary) -> void:
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = _rgb(cam_block, "Light", Color(1, 1, 0.88))
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 800.0
	sun.rotation_degrees = Vector3(-float(cam_block.get("LightDirPitch", 50.0)), -float(cam_block.get("LightDirYaw", 11.0)), 0)
	add_child(sun)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	var sky := ProceduralSkyMaterial.new()
	# Below the horizon, continue the sea past the map edge instead of the default brown ground.
	sky.ground_bottom_color = Color(0.05, 0.14, 0.2)
	sky.ground_horizon_color = Color(0.32, 0.42, 0.48)
	sky.sky_horizon_color = Color(0.66, 0.72, 0.78)
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = _rgb(cam_block, "Ambient", Color(0.28, 0.28, 0.31))
	env.ambient_light_energy = 1.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ssao_enabled = true
	env.glow_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)


func _rgb(block: Dictionary, prefix: String, fallback: Color) -> Color:
	if not block.has(prefix + "Red"):
		return fallback
	return Color8(int(block[prefix + "Red"]), int(block[prefix + "Green"]), int(block[prefix + "Blue"]))


func _build_hud() -> void:
	hud = MissionHud.new()
	add_child(hud)
	hud.setup(self)
	input.box = hud.box
	var markers := ObjectiveMarkers.new()
	markers.name = "ObjectiveMarkers"
	add_child(markers)
	markers.setup(sm.objectives, world.map)
