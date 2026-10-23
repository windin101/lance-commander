extends Node
## Dev probe for the ground "speckle" squares (phase 8): opens a mission, flies the camera over it and
## saves frames, with render layers switched off one at a time.
##   godot --path game res://tools/speckle_probe.tscn -- --mission=mc2_02 --no-hud --seconds=60
##       --every=3 --out=/mnt/nvme1n1p1/mc2-speckle/run --off=detail,overlay,... [--demo]
## --off keys: detail (ground_detail grain+relief), detailmap (the original detail texture), rock,
## overlay, cement, decals, trees, objects, water, shadows, ssao, glow, fog, effects, units, sky
## --aa=msaa2|msaa4|taa|fxaa|fsr  turns an AA/scaling mode on. --debug-view=N sets the terrain debug_view.
## --log-radio prints each pilot radio line as it starts (time, pilot, stem).

var _args := {}
var _view: Node3D
var _t := 0.0
var _frame := 0
var _saved := 0
var _home := Vector3.ZERO


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	get_window().size = Vector2i(1920, 1080)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	_view = load("res://scenes/mission_view.tscn").instantiate()
	_view.play_intro = false
	add_child(_view)
	await get_tree().process_frame
	await get_tree().process_frame
	_apply_off(String(_args.get("off", "")).split(",", false))
	var aa := String(_args.get("aa", ""))
	var vp := get_viewport()
	match aa:
		"msaa2": vp.msaa_3d = Viewport.MSAA_2X
		"msaa4": vp.msaa_3d = Viewport.MSAA_4X
		"taa": vp.use_taa = true
		"fxaa": vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
		"fsr": vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
	if _args.has("debug-view"):
		_ground_mat().set_shader_parameter("debug_view", int(_args["debug-view"]))
	DirAccess.make_dir_recursive_absolute(String(_args.get("out", "/mnt/nvme1n1p1/mc2-speckle/run")))
	_home = _view.camera.focus
	if _args.has("log-radio"):
		_view.audio.radio_line.connect(func(u, stem): print("RADIO %.1f %s %s" % [_view.world.time, u.pilot_profile, stem]))
	print("PROBE ready off=", _args.get("off", ""), " aa=", aa)


func _ground_mat() -> ShaderMaterial:
	return (_view.terrain.get_node("Ground") as MeshInstance3D).material_override as ShaderMaterial


func _apply_off(keys: PackedStringArray) -> void:
	var gm := _ground_mat()
	var env: Environment = _view._env
	for k in keys:
		match k:
			"detail":
				gm.set_shader_parameter("ground_detail", 0.0)
				gm.set_shader_parameter("ground_relief", 0.0)
			"detailmap": gm.set_shader_parameter("detail_strength", 0.0)
			"rock": gm.set_shader_parameter("rock_grain", 0.0)
			"overlay": gm.set_shader_parameter("vertices_per_side", 0.0)
			"cement":
				var img := Image.create(1, 1, false, Image.FORMAT_R8)
				gm.set_shader_parameter("cement_weight", ImageTexture.create_from_image(img))
			"decals": _view.decals.visible = false
			"trees":
				for c in _view.objects_view.get_children():
					if c is MultiMeshInstance3D: c.visible = false
			"objects": _view.objects_view.visible = false
			"water":
				for n in ["Water", "WaterSkirt"]:
					var w = _view.terrain.get_node_or_null(n)
					if w: w.visible = false
			"shadows": _view._sun.shadow_enabled = false
			"ssao": env.ssao_enabled = false
			"glow": env.glow_enabled = false
			"fog": env.fog_enabled = false
			"effects": _view.effects.visible = false
			"units":
				for v in _view.views.values(): v.visible = false
			_: push_warning("unknown --off key " + k)


func _process(delta: float) -> void:
	if _view == null or _view.camera == null:
		return
	_t += delta
	var cam = _view.camera
	cam.limits = false
	var r := float(_args.get("radius", "300"))
	# a slow lissajous around the player's start, the yaw turning, the zoom breathing between near and far
	cam.focus = _home + Vector3(r * sin(_t * 0.11), 0, r * sin(_t * 0.07 + 1.0))
	cam.yaw_deg = fmod(_t * 6.0, 360.0)
	cam.pitch_deg = 35.0 + 15.0 * sin(_t * 0.13)
	cam.distance = 180.0 + 120.0 * (0.5 + 0.5 * sin(_t * 0.17))
	_frame += 1
	if _frame > 20 and _frame % int(_args.get("every", "3")) == 0:
		_capture.call_deferred()
	if _t > float(_args.get("seconds", "60")):
		print("PROBE done frames=", _frame, " saved=", _saved)
		get_tree().quit()


func _capture() -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := "%s/f%05d.png" % [String(_args.get("out", "/mnt/nvme1n1p1/mc2-speckle/run")), _frame]
	img.save_png(path)
	_saved += 1
