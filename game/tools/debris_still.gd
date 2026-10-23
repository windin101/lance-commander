extends Node3D
## Dev still for explosion debris (phase 8): a few EffectsView debris particles hung in the air close to
## the camera, gravity off, captured once their glow has cooled.
##   godot --path game res://tools/debris_still.tscn -- --out=/path/still.png [--age=1.2] [--dist=5]

var _args := {}
var _fx: EffectsView
var _t := 0.0
var _done := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	get_window().size = Vector2i(1280, 720)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.45, 0.5, 0.55)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.3, 0.3, 0.33)
	env.ambient_light_energy = 1.5
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	add_child(sun)
	sun.look_at_from_position(Vector3.ZERO, Vector3(-0.4, -0.7, -0.5), Vector3.UP)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(40, 40)
	ground.mesh = pm
	var gmat := StandardMaterial3D.new()
	gmat.albedo_color = Color(0.36, 0.33, 0.27)
	ground.material_override = gmat
	add_child(ground)
	var cam := Camera3D.new()
	var d := float(_args.get("dist", "5"))
	add_child(cam)
	cam.look_at_from_position(Vector3(0, 1.0 + d * 0.45, d), Vector3(0, 0.9, 0), Vector3.UP)
	cam.fov = 50.0
	_fx = EffectsView.new()
	add_child(_fx)
	var e: GPUParticles3D = _fx._emitters["debris"]
	(e.process_material as ShaderMaterial).set_shader_parameter("gravity", 0.0)
	(e.process_material as ShaderMaterial).set_shader_parameter("spin", float(_args.get("spin", "0.6")))
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	var cols := [Color("#3a3836"), Color("#4a4440"), Color("#2e2c2a"), Color("#5a5048")]
	for i in 14:
		var p := Vector3(rng.randf_range(-2.2, 2.2), rng.randf_range(0.4, 1.8), rng.randf_range(-1.5, 1.0))
		_fx.emit("debris", p, Vector3.ZERO, cols[i % cols.size()], rng.randf_range(0.35, 0.75), 4.0)


func _process(delta: float) -> void:
	_t += delta
	if not _done and _t >= float(_args.get("age", "1.2")):
		_done = true
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(String(_args.get("out", "/mnt/nvme1n1p1/mc2-speckle/debris.png")))
		print("saved debris still")
		get_tree().quit()
