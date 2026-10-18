extends Node3D
## Shows a converted mech model in a lit studio, for screenshots.
## User args: --model=res://assets/mechs/bushwacker.glb --anim=Walk --t=0.25
## Concept-render options: --bg=r,g,b (0-1) --no-ground --fov=<deg> --focus-y=<m> --focus-xz=<x>,<z>
## Pass --cam=yaw,pitch,distance to DevTools to frame it.

var camera: RtsCamera


func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var model: Node3D = load(args.get("model", "res://assets/mechs/bushwacker.glb")).instantiate()
	add_child(model)
	if args.has("paint"):  # --paint=<model name>,<red argb>,<green argb>,<blue argb>
		var v: PackedStringArray = args["paint"].split(",")
		var folder := "vehicles" if String(args.get("model", "")).contains("/vehicles/") else "mechs"
		MechPaint.apply(model, v[0], MechPaint.argb(int(v[1])), MechPaint.argb(int(v[2])), MechPaint.argb(int(v[3])), folder)
	var player: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	if player and args.has("anim"):
		player.play(args["anim"])
		player.seek(float(args.get("t", "0")), true)
		player.pause()

	var no_ground := args.has("no-ground")
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 60)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.45, 0.42, 0.36)
	ground.material_override = gm
	if not no_ground:
		add_child(ground)
	var grid := MeshInstance3D.new()  # 1 m ticks along X for scale
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_LINES)
	for i in range(-10, 11):
		st.add_vertex(Vector3(i, 0.02, -0.3))
		st.add_vertex(Vector3(i, 0.02, 0.3))
	grid.mesh = st.commit()
	if not no_ground:
		add_child(grid)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.shadow_enabled = true
	add_child(sun)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.2, 0.22, 0.26)
	if args.has("bg"):
		var c: PackedStringArray = args["bg"].split(",")
		env.background_color = Color(float(c[0]), float(c[1]), float(c[2]))
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.5, 0.5, 0.55)
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	camera = RtsCamera.new()
	camera.name = "Camera"
	camera.focus = Vector3(0, 0, 0)
	camera.distance = 22.0
	camera.min_distance = 2.0
	camera.pitch_deg = 15.0
	camera.yaw_deg = 200.0
	add_child(camera)
	camera.make_current()
	_focus_y = float(args.get("focus-y", "4"))
	camera.focus = Vector3(0, _focus_y, 0)
	if args.has("focus-xz"):  # off-centre models (buildings)
		var xz: PackedStringArray = args["focus-xz"].split(",")
		camera.focus = Vector3(float(xz[0]), _focus_y, float(xz[1]))
	if args.has("fov"):
		camera.fov = float(args["fov"])


var _focus_y := 4.0


func _process(_delta: float) -> void:
	camera.focus.y = _focus_y
