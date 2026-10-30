extends Node
## Dev (LANCE-19): a real mission on the real boot path, one close shot per vehicle model found in it, for the v3-vs-old-art
## comparison. Run it twice, with and without --no-art-v3 (and --no-hd for the 2001 models if wanted).
##   godot --path game res://scenes/vehicle_mission_shots.tscn -- --mission=mc2_16 --models=lrmc,centipede,harasser,partisan,storm
##        --out=/abs/prefix [--dist=40] [--pitch=40] [--yaw=20] [--no-art-v3]
## Writes <out>_<model>.png. The camera is moved onto the first unit of that model; the sim is frozen after --warm=<n> ticks.

var _args := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var camp := Campaign.create(GameData)
	var slot := 1
	for entry in "atlas:pmwhacksaw,madcat:pmwlongshot,bushwacker:pmwflash,catapult:pmwjinx".split(","):
		var bits := entry.split(":")
		camp.add_mech(bits[0], 0, bits[1], slot)
		slot += 1
	var view: Node = load("res://scenes/mission_view.tscn").instantiate()
	view.mission = String(_args.get("mission", "mc2_16"))
	view.force = camp.force()
	view.name = "MissionView"
	add_child(view)
	_run.call_deferred(view)


func _run(view: Node) -> void:
	for i in 40:
		await get_tree().process_frame
	var w: SimWorld = view.world
	var cam: RtsCamera = view.camera
	cam.limits = false
	cam.yaw_deg = float(_args.get("yaw", 20.0))
	cam.pitch_deg = float(_args.get("pitch", 40.0))
	cam.distance = float(_args.get("dist", 40.0))
	for m in String(_args.get("models", "lrmc")).split(","):
		var found: Array = w.units.filter(func(u): return u.model == m)
		if found.is_empty():
			push_warning("vehicle_mission_shots: no %s in %s" % [m, view.mission])
			continue
		var u: SimUnit = found[0]
		cam.pan_to(u.position)
		for i in 30:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		img.save_png("%s_%s.png" % [_args.get("out", "/tmp/vms"), m])
		print("shot ", m, " at ", u.position, " (", found.size(), " in mission)")
	get_tree().quit()
