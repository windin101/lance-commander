extends Node3D
## A playable mission: terrain, map objects, mechs, effects, RTS commands.
## The SimWorld steps at a fixed 10 Hz; views interpolate between ticks.
## Dev args: --mission=mc2_NN, --no-hud, --demo (player lance attacks the nearest enemy), --arena (moves the
## Starslayer onto open ground 110 m north of the lance first), --sim-seconds=N
## (fast-forward before the first frame), --focus=player|battle, --kill-unit=N
## (destroy unit N at start and frame its wreck), --sim-until-shots=N (fast-forward until N shots are fired), --freeze (the sim does not step; the fx range drives it).

@export var mission := "mc2_01"
@export var play_intro := true
var force: Array = []  # the campaign's chosen mechs (Flow); empty: the mission's own units  # opening flyby; tests and dev runs switch it off

var sm: SimMission
var world: SimWorld
var terrain: TerrainView
var objects_view: ObjectsView
var decals: DecalsView
var effects: EffectsView
var input: CommandInput
var camera: RtsCamera
var compass: CameraCompass
var views: Dictionary = {}  # mech id -> MechView
var hud: MissionHud
var audio: AudioDirector
var flyby: IntroFlyby
var pause_menu: PauseMenu
var title := ""  # the mission's display name (briefing title)
var _end_seen_at := -1.0
var _videos: Dictionary = {}  # comms clip name -> res:// path (retail disc, if converted)
var _acc := 0.0
var _skip_movie := false  # dev runs and tests: the mission script's cinematic is skipped as by Esc
var _args := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	if _args.has("mission"):  # dev: open any converted mission directly
		mission = String(_args["mission"])
	sm = SimMission.load_mission(GameData, mission, 1, true, force)
	world = sm.world
	var mission_fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % mission))
	var cam_block: Dictionary = mission_fit.get("Cameras", {})

	terrain = TerrainView.new()
	terrain.name = "Terrain"
	add_child(terrain)
	terrain.water_fit = mission_fit.get("Water", {})
	terrain.water_detail_tiling = float(mission_fit.get("Terrain", {}).get("WaterDetailTilingFactor", 45.0))
	terrain.build(world.map, "res://assets/maps/%s" % mission)
	MechPaint.set_environment_for(mission)  # dust and snow on v2 units
	objects_view = ObjectsView.new()
	objects_view.name = "Objects"
	add_child(objects_view)
	objects_view.build(world.map, mission)
	decals = DecalsView.new()
	decals.name = "Decals"
	add_child(decals)
	decals.setup(world.map)
	_lighting(cam_block, mission_fit)

	effects = EffectsView.new()
	effects.name = "Effects"
	add_child(effects)
	effects.setup(world.map)
	for m in world.units:
		if m.is_mover():
			_add_view(m)
		elif m is SimTurret:
			_turrets.append(m)

	camera = RtsCamera.new()
	camera.name = "Camera"
	camera.far = 6000.0
	camera.bounds_half = world.map.half_m
	camera.height_at = world.map.height_at
	camera.yaw_deg = RtsCamera.from_original_yaw(float(cam_block.get("StartRotation", 180.0)))
	camera.home_yaw = camera.yaw_deg
	camera.distance = RtsCamera.DEFAULT_DISTANCE
	camera.pitch_deg = RtsCamera.DEFAULT_PITCH
	# The original's projection: perspective, 40 deg HORIZONTAL field of view (Camera.cpp:499).
	camera.keep_aspect = Camera3D.KEEP_WIDTH
	camera.fov = 40.0
	camera.input_blocked = _cinematic
	camera.follow_pos = func(u: SimUnit) -> Vector3:
		return views[u.id].global_position if views.has(u.id) else Vector3(u.position.x, 0, -u.position.y)
	add_child(camera)
	camera.make_current()
	_focus_player()
	compass = CameraCompass.new()
	compass.name = "Compass"
	add_child(compass)
	compass.setup(camera, _cinematic)
	var weather := WeatherView.new()
	weather.name = "Weather"
	add_child(weather)
	weather.setup(mission_fit.get("Weather", {}), camera, _sun, _env)

	input = CommandInput.new()
	input.world = world
	input.views = views
	input.camera = camera
	input.player_team = sm.player_team
	input.abl = sm.abl
	input.support = sm.support
	add_child(input)
	_build_hud()
	if _args.has("no-hud"):  # dev: clean frames for HUD mock-ups and screenshots
		hud.offset = Vector2(100000, 0)  # moves every HUD canvas item off-screen
	audio = AudioDirector.new()
	audio.name = "Audio"
	add_child(audio)
	var bcfg_path := "res://data/brains/%s.json" % mission
	var script_cfg: Dictionary = {}
	if FileAccess.file_exists(bcfg_path):
		script_cfg = JSON.parse_string(FileAccess.get_file_as_string(bcfg_path)).get("script", {})
	if FileAccess.file_exists("res://data/videos.json"):
		_videos = JSON.parse_string(FileAccess.get_file_as_string("res://data/videos.json"))
	if sm.abl:
		# The mission script waits on isPlayingVoiceOver between its tutorial stages.
		sm.abl.voice_busy = func() -> bool:
			return audio.voice.playing or not audio._voice_queue.is_empty() or hud.comms.is_playing()
	var dev_run := not play_intro or ((_args.has("demo") or _args.has("arena") or _args.has("sim-seconds") or _args.has("screenshot")) and not _args.has("flyby"))
	_skip_movie = dev_run
	flyby = IntroFlyby.new()
	flyby.name = "Flyby"
	add_child(flyby)
	flyby.setup(self, {} if dev_run else script_cfg.get("flyby", {}), float(cam_block.get("StartRotation", 180.0)))
	title = MissionBrief.load_mission(GameData, mission).title
	pause_menu = PauseMenu.new()
	pause_menu.name = "PauseMenu"
	pause_menu.view = self
	add_child(pause_menu)

	if _args.has("arena"):
		_arena()
	if _args.has("demo"):
		_demo_orders()
	var ff := float(_args.get("sim-seconds", "0"))
	var until_shots := int(_args.get("sim-until-shots", "0"))  # dev (perf): fast-forward into the battle
	if until_shots > 0:
		ff = maxf(ff, 900.0)
	while ff > 0.0:
		if world.movie_mode:
			world.force_movie_end = true  # a dev run: skip the script's cinematic (as Esc)
		sm.step()
		for e in world.events:
			if e["type"] == "shot":
				until_shots -= 1
		_consume_events(false)
		ff -= SimWorld.TICK
		if until_shots <= 0 and _args.has("sim-until-shots"):
			break
	if _args.get("focus", "") == "battle":
		_focus_battle()
	if _args.has("kill-unit"):  # dev: destroy a unit at start and frame it (wreck checks)
		var u: SimUnit = world.units[int(_args["kill-unit"])]
		u.status = SimUnit.Status.DESTROYED
		camera.focus = Vector3(u.position.x, 0, -u.position.y)
	if _args.has("select-all"):
		input._set_selection(world.units.filter(func(u): return u.team == sm.player_team and u.is_mover() and not u.is_disabled()))
	for v in views.values():
		v.sync(1.0)


var _turrets: Array[SimTurret] = []  # map turrets: their guns turn in the view


func _process(delta: float) -> void:
	_update_haze()
	_acc += delta
	if _args.has("freeze"):  # dev (fx range): the sim stands still, effects are driven by hand
		_acc = 0.0
	while _acc >= SimWorld.TICK:
		# Skipping the opening flyby, or a dev run that has none, skips the script's movie as Esc does
		# (forceMovieEnd, missiongui.cpp:435-436); the script fades and calls endMovieMode itself.
		if world.movie_mode and (_skip_movie or flyby.skipped):
			world.force_movie_end = true
		sm.step()
		_acc -= SimWorld.TICK
	var alpha := _acc / SimWorld.TICK
	for v in views.values():
		v.sync(alpha)
	for t in _turrets:
		objects_view.set_turret_yaw(t.object_index, t.turret_yaw, t.facing)
	_consume_events(true)
	if audio:
		audio.tick(world.time)
		if sm.abl == null:  # otherwise the mission script picks the music (playDigitalMusic)
			audio.update_music(sm.objectives.result, world.time)
	# Mission over: after the banner has been up a moment, offer the debrief.
	if sm.objectives.result != SimObjectives.Result.PLAYING and pause_menu and not pause_menu.ended:
		if _end_seen_at < 0.0:
			_end_seen_at = world.time
		elif world.time - _end_seen_at >= 3.0:
			pause_menu.show_end(sm.objectives.result == SimObjectives.Result.WON)


## A cinematic owns the camera: the opening flyby or ABL movie mode (missiongui.cpp:430).
func _cinematic() -> bool:
	return (world != null and world.movie_mode) or (flyby != null and flyby.is_running())


## The debrief's facts for this mission so far (MissionReport).
func report() -> Dictionary:
	return MissionReport.from_sim(sm, title, GameData)


func _add_view(m: SimUnit) -> void:
	var v := MechView.new()
	add_child(v)
	v.setup(m, world.map)
	views[m.id] = v
	if effects:
		effects.track(v)
	var foot_m := 1.25 * (1.6 + 0.024 * float(m.get("tonnage") if m.get("tonnage") != null else 50.0))  # 3.5 m at 50 t, 5 m at 100 t
	v.footstep.connect(func(at: Vector3) -> void:
		if audio:
			audio.sfx("footstep", at, -10.0)
		if decals and m is SimMech:
			decals.footstep(m.id, m.model, v.global_transform, foot_m))


func _consume_events(show: bool) -> void:
	for e in world.events:
		# Units that join mid-mission need views even while fast-forwarding.
		match e["type"]:
			"unit_added":
				_add_view(world.units[e["unit"]])
			"salvaged":
				if views.has(e["unit"]):
					views[e["unit"]].queue_free()
				_add_view(world.units[e["unit"]])
		if not show:
			continue
		if hud:
			hud.on_event(e)
		if audio:
			_audio_event(e)
		match e["type"]:
			"shot":
				# movers have views; turrets and buildings are drawn by ObjectsView
				if not ((views.has(e["from"]) or world.units[e["from"]] is SimStructure) \
						and (views.has(e["to"]) or world.units[e["to"]] is SimStructure)):
					continue
				_shot_effect(e)
			"blast", "mine":
				# an area-effect shell (Long Tom, Swarm LRM) or a mine going off
				var p: Vector2 = e["at"]
				var big: bool = e["type"] == "mine" or float(e.get("radius", 0.0)) >= 30.0
				if big:
					effects.burst("strike_blast", TerrainView.to_3d(p, world.map.height_at(p) + 1.0))
				if decals:
					decals.crater(p, 10.0 if big else 6.0, true)
			"strike_impact":
				var p: Vector2 = e["at"]
				effects.burst("strike_blast", TerrainView.to_3d(p, world.map.height_at(p) + 1.0))
				if decals:
					decals.crater(p, 16.0)
					decals.crater(p, 24.0, true)
			"support":
				if e["kind"] == "air_strike":
					var p: Vector2 = e["at"]
					effects.burst("marker_flash", TerrainView.to_3d(p, world.map.height_at(p) + 1.0))
			"disabled":
				var u: SimUnit = world.units[e["unit"]]
				if decals:
					decals.crater(u.position, 18.0 if u is SimStructure else 10.0, true)
				if u is SimStructure:
					var box: AABB = objects_view.bounds(u.object_index)
					objects_view.destroy(u.object_index)
					var base := TerrainView.to_3d(u.position, world.map.height_at(u.position))
					var size := 1.0
					var height := 10.0
					if box.size.length() > 0.1:
						base = Vector3(box.get_center().x, box.position.y, box.get_center().z)
						size = clampf(maxf(box.size.x, box.size.z) / 14.0, 0.6, 3.0)
						height = box.size.y
					effects.destroyed("building", base, size, height)
				elif views.has(e["unit"]):
					var v: MechView = views[e["unit"]]
					effects.destroyed("mech" if u is SimMech else "vehicle", v.global_position, v.fx_scale(), v.bounds.size.y)
	world.events.clear()


## The visible shot (I87): the weapon's own effect from its muzzle node to the body location it hit, or into
## the ground past the target; misses leave a crater or scorch where they land.
func _shot_effect(e: Dictionary) -> void:
	var shooter: SimUnit = world.units[e["from"]]
	var item: Dictionary = shooter.items[e["weapon"]]
	var fx_id := int(item["component"].get("weapon", {}).get("special_fx", 0))
	var opts := {"component": int(item["master_id"])}
	var muzzle: Variant = null
	if views.has(e["from"]):
		var from: MechView = views[e["from"]]
		var node := from.muzzle_node(e["weapon"])
		if node:
			opts["from_node"] = node
		muzzle = from.muzzle_point(e["weapon"])
	else:
		muzzle = _structure_point(shooter, 0.8)  # turrets and armed buildings
	var aim: Variant = null
	if views.has(e["to"]):
		var to: MechView = views[e["to"]]
		opts["to_node"] = to
		aim = to.body_point(int(e.get("location", 1))) if e["hit"] else to.aim_point()
	else:
		aim = _structure_point(world.units[e["to"]], 0.5)
	if muzzle == null or aim == null:
		return
	if decals:
		opts["on_ground"] = func(at: Vector3, size_m: float, scorch: bool) -> void:
			decals.crater(Vector2(at.x, -at.z), size_m, scorch)
	effects.fire(fx_id, muzzle, aim, e["hit"], e["flight"], opts)


## A point at height fraction `up` of a map structure's model (null: no model).
func _structure_point(u: SimUnit, up: float) -> Variant:
	if not (u is SimStructure) or objects_view == null:
		return null
	var box: AABB = objects_view.bounds(u.object_index)
	if box.size.length() < 0.1:
		return TerrainView.to_3d(u.position, world.map.height_at(u.position) + 4.0 * up)
	var c := box.get_center()
	return Vector3(c.x, box.position.y + box.size.y * up, c.z)


func _audio_event(e: Dictionary) -> void:
	match e["type"]:
		"shot":
			var shooter: SimUnit = world.units[e["from"]]
			if views.has(e["from"]) or shooter is SimTurret:
				var at: Vector3 = views[e["from"]].global_position if views.has(e["from"]) \
					else TerrainView.to_3d(shooter.position, world.map.height_at(shooter.position) + 4.0)
				audio.weapon_fire(int(shooter.items[e["weapon"]]["master_id"]), at)
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
		"mission_end":
			audio.announce("win" if e["won"] else "lose")
		# Presentation from the mission's ABL (SimAbl natives)
		"abl_wave":
			audio.say(String(e["file"]).replace("\\", "/").get_file().get_basename().to_lower())
		"abl_music":
			audio.play_tune(int(e["id"]))
		"abl_video":
			var clip := String(e["file"]).get_basename().to_lower()
			if hud and _videos.has(clip):
				hud.comms.play(String(_videos[clip]))


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


func _lighting(cam_block: Dictionary, fit_data: Dictionary = {}) -> void:
	# The sun, from the mission's [Cameras] LightDirYaw/Pitch the way the original computed it
	# (Camera.cpp:1505-1509): toward the light = (cos(yaw+45), sin(yaw+45), sin(pitch)) in MC2's x east,
	# y north, z up. That is the direction the burnt-in colour map was shaded from, so dynamic shadows of
	# mechs and objects fall the same way as the painted ones. Night missions (pitch 270) light from below
	# in the original; objects here take the mirrored, low sun instead.
	var yaw := deg_to_rad(float(cam_block.get("LightDirYaw", 11.0)) + 45.0)
	var pitch := deg_to_rad(float(cam_block.get("LightDirPitch", 50.0)))
	var to_light := Vector3(cos(yaw), maxf(absf(sin(pitch)), 0.2), -sin(yaw)).normalized()  # Godot: -Z is north
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = _rgb(cam_block, "Light", Color(1, 1, 0.88))
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 800.0
	add_child(sun)
	_sun = sun
	sun.look_at_from_position(Vector3.ZERO, -to_light, Vector3.UP if absf(to_light.y) < 0.99 else Vector3.FORWARD)
	var ground := terrain.get_node_or_null("Ground") as MeshInstance3D
	if ground and ground.material_override is ShaderMaterial:
		(ground.material_override as ShaderMaterial).set_shader_parameter("sun_dir", to_light)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	# The original's skybox for [TheSky] SkyNumber, as a panorama (tools/art/env_textures.py)
	var sky_n := int(fit_data.get("TheSky", {}).get("SkyNumber", 1))
	var pano_path := "res://assets/sky/sky%02d.png" % sky_n
	if ResourceLoader.exists(pano_path):
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = load(pano_path)
		env.sky.sky_material = pano
	else:
		var sky := ProceduralSkyMaterial.new()
		sky.ground_bottom_color = Color(0.05, 0.14, 0.2)
		sky.ground_horizon_color = Color(0.32, 0.42, 0.48)
		sky.sky_horizon_color = Color(0.66, 0.72, 0.78)
		env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = _rgb(cam_block, "Ambient", Color(0.28, 0.28, 0.31))
	env.ambient_light_energy = 1.75  # 1.6 under the old filmic curve; the linear curve shows it as is
	# Linear: the terrain shows its colour map as painted (the original had no tone curve); filmic dimmed
	# and desaturated it.
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.ssao_enabled = true
	env.glow_enabled = true
	# Fog: the original's distance haze (MinHazeDistance 600 m to MaxClipDistance 800 m from its camera) in
	# the mission's FogColor, kept relative to the zoom (see _process), plus its height fog where the mission
	# sets FogStart/FogFull (elevations, world units; -1/-2 = off). quad.cpp:880-929.
	var fog_c := int(cam_block.get("FogColor", 0xd0d4dc))
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color8((fog_c >> 16) & 255, (fog_c >> 8) & 255, fog_c & 255)
	env.fog_light_energy = 1.0
	env.fog_density = 0.6
	env.fog_sky_affect = 0.25
	env.fog_depth_curve = 1.6
	var fog_start := float(cam_block.get("FogStart", -1.0))
	var fog_full := float(cam_block.get("FogFull", -2.0))
	if fog_start > fog_full and not (is_equal_approx(fog_start, -1.0) and is_equal_approx(fog_full, -2.0)):
		env.fog_height = fog_start * world.map.meters_per_wu
		env.fog_height_density = 1.0 / maxf(1.0, (fog_start - fog_full) * world.map.meters_per_wu)
	_env = env
	_update_haze()
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)


var _env: Environment
var _sun: DirectionalLight3D


func _update_haze() -> void:
	if _env == null:
		return
	var d := camera.distance if camera else RtsCamera.DEFAULT_DISTANCE
	_env.fog_depth_begin = d + 600.0
	_env.fog_depth_end = d + 2600.0


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
