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
var hud: Label
var objectives_label: Label
var banner: Label
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
	_update_hud()


func _consume_events(show: bool) -> void:
	for e in world.events:
		if not show:
			continue
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


func _demo_orders() -> void:
	for m in world.units:
		if m.team != sm.player_team:
			continue
		var best: SimMech = null
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
	env.sky.sky_material = ProceduralSkyMaterial.new()
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
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = Label.new()
	hud.position = Vector2(16, 12)
	hud.add_theme_font_size_override("font_size", 16)
	hud.add_theme_color_override("font_outline_color", Color.BLACK)
	hud.add_theme_constant_override("outline_size", 4)
	layer.add_child(hud)
	objectives_label = Label.new()
	objectives_label.anchor_left = 1.0
	objectives_label.anchor_right = 1.0
	objectives_label.offset_left = -520
	objectives_label.offset_right = -16
	objectives_label.offset_top = 12
	objectives_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	objectives_label.add_theme_font_size_override("font_size", 17)
	objectives_label.add_theme_color_override("font_outline_color", Color.BLACK)
	objectives_label.add_theme_constant_override("outline_size", 4)
	layer.add_child(objectives_label)
	banner = Label.new()
	banner.set_anchors_preset(Control.PRESET_CENTER)
	banner.add_theme_font_size_override("font_size", 64)
	banner.add_theme_color_override("font_outline_color", Color.BLACK)
	banner.add_theme_constant_override("outline_size", 10)
	banner.visible = false
	layer.add_child(banner)
	var box := ColorRect.new()
	box.color = Color(0.3, 1.0, 0.4, 0.15)
	box.visible = false
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(box)
	input.box = box


func _update_hud() -> void:
	var lines: Array[String] = ["%s  —  t %.0f s   (left-click/drag select, right-click move/attack, H hold)" % [mission, world.time]]
	var shown: Array = input.selection if not input.selection.is_empty() else world.units.filter(func(m): return m.team == sm.player_team and m.is_mover())
	for m in shown:
		var armor := 0.0
		var max_armor := 0.0
		for i in m.armor.size():
			armor += m.armor[i]
			max_armor += m.max_armor[i]
		var status: String = ["OK", "SHUTDOWN", "DISABLED", "DESTROYED"][m.status]
		if m is SimMech and m.fallen and not m.is_disabled():
			status = "FALLEN"
		lines.append("%-10s %-9s armour %3d%%  heat %2d/30  %s" % [m.name, status, int(100.0 * armor / maxf(max_armor, 1.0)),
			m.heat_level(), ("-> " + m.current_target.name) if m.current_target and not m.current_target.is_disabled() else ""])
	hud.text = "\n".join(lines)
	var obj_lines: Array[String] = ["OBJECTIVES"]
	for obj in sm.objectives.visible_objectives():
		var title: String = GameData.string(obj["title_string"]) if obj["title_string"] > 0 else obj["title"]
		if title.is_empty():
			title = obj["title"]
		obj_lines.append(("[x] " if obj["complete"] else "[ ] ") + title)
	objectives_label.text = "\n".join(obj_lines)
	var res := sm.objectives.result
	if res != SimObjectives.Result.PLAYING and not banner.visible:
		banner.visible = true
		banner.text = "MISSION SUCCESSFUL" if res == SimObjectives.Result.WON else "MISSION FAILED"
		banner.add_theme_color_override("font_color", Color(0.5, 1.0, 0.5) if res == SimObjectives.Result.WON else Color(1.0, 0.4, 0.3))
		banner.position = get_viewport().get_visible_rect().size / 2.0 - banner.get_minimum_size() / 2.0
