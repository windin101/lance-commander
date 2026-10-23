extends Node
## Developer hooks driven by user command-line arguments (after "--"):
##   --screenshot=<path>   render, save a PNG, quit
##   --frames=<n>          frames to wait first (default 40)
##   --size=<w>x<h>        window size for the shot (default 1600x900)
##   --wait-effects=<n>    then keep waiting (up to 20 s) until the scene's "Effects"
##                         node has at least n live effects (EffectsView.live_count)
##   --cam=yaw,pitch,distance[,x,y]   camera override for the current scene's "Camera"
##   --perf=<seconds>      measure frame time (CPU wall and GPU render, vsync off) for that long after
##                         --frames, print a JSON summary (and write it to --perf-out=<path>), quit
## Example:
##   godot --path game res://scenes/mission_view.tscn -- --screenshot=/tmp/a.png --cam=0,70,1300

var _args := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	if _args.has("screenshot"):
		_take_screenshot.call_deferred()
	elif _args.has("perf"):
		_measure_perf.call_deferred()


func _measure_perf() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var vp := get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	for i in int(_args.get("frames", "40")):
		await get_tree().process_frame
	var scene := get_tree().current_scene
	var seconds := float(_args["perf"])
	var wall: Array[float] = []
	var gpu: Array[float] = []
	var live_max := 0
	var start := Time.get_ticks_usec()
	var last := start
	while float(last - start) / 1e6 < seconds:
		await get_tree().process_frame
		var now := Time.get_ticks_usec()
		wall.append(float(now - last) / 1000.0)
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
		last = now
		var fx = scene.get_node_or_null("Effects") if scene else null
		if fx:
			live_max = maxi(live_max, fx.live_count() if fx.has_method("live_count") else fx.get_child_count())
	var out := {"frames": wall.size(), "seconds": seconds, "wall_ms": _stats(wall), "gpu_ms": _stats(gpu),
		"effects_live_max": live_max}
	var fx = scene.get_node_or_null("Effects") if scene else null
	if fx and fx.has_method("stats"):
		out["effects"] = fx.stats()
	print("PERF ", JSON.stringify(out))
	if _args.has("perf-out"):
		var f := FileAccess.open(_args["perf-out"], FileAccess.WRITE)
		f.store_string(JSON.stringify(out, "  "))
	get_tree().quit()


static func _stats(v: Array[float]) -> Dictionary:
	if v.is_empty():
		return {}
	var s := v.duplicate()
	s.sort()
	var total := 0.0
	for x in s:
		total += x
	return {"mean": snappedf(total / s.size(), 0.01), "p50": snappedf(s[s.size() / 2], 0.01),
		"p95": snappedf(s[int(s.size() * 0.95)], 0.01), "p99": snappedf(s[int(s.size() * 0.99)], 0.01),
		"max": snappedf(s[-1], 0.01)}


func _take_screenshot() -> void:
	var sz: PackedStringArray = String(_args.get("size", "1600x900")).split("x")
	get_window().size = Vector2i(int(sz[0]), int(sz[1])) if sz.size() == 2 else Vector2i(1600, 900)
	await get_tree().process_frame
	var scene := get_tree().current_scene
	var cam = scene.get_node_or_null("Camera") if scene else null
	if cam and _args.has("cam"):
		var v: PackedStringArray = _args["cam"].split(",")
		if "limits" in cam: cam.limits = false  # overview shots may sit outside the play limits
		cam.yaw_deg = float(v[0])
		if v.size() > 1: cam.pitch_deg = float(v[1])
		if v.size() > 2: cam.distance = float(v[2])
		if v.size() > 4: cam.focus = Vector3(float(v[3]), 0, -float(v[4]))
	for i in int(_args.get("frames", "40")):
		await get_tree().process_frame
	if _args.has("wait-effects") and scene:
		var fx := scene.get_node_or_null("Effects")
		var need := int(_args["wait-effects"])
		var waited := 0.0
		while fx and (fx.live_count() if fx.has_method("live_count") else fx.get_child_count()) < need and waited < 20.0:
			await get_tree().process_frame
			waited += get_process_delta_time()
	await RenderingServer.frame_post_draw
	var path: String = _args["screenshot"]
	get_viewport().get_texture().get_image().save_png(path)
	print("saved ", path)
	get_tree().quit()
