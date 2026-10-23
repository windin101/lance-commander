extends Node
## Batch renders of unit and object models in the Mech Bay studio (MechStage.Studio: same lights, paint and
## framing as the bay and the lab), many shots per Godot run. For the HD rework audit and review sheets.
##   godot --path game res://scenes/art_gallery.tscn -- --job=/abs/job.json
## job.json: {"size": [w, h], "items": [{"path": "res://assets/mechs/bushwacker_hd.glb", "paint_name": "bushwacker_hd",
##   "folder": "mechs", "paint": [hl1, hl2, base] (ARGB ints, optional), "out": "/abs/prefix",
##   "shots": [{"name": "a", "yaw": -22, "fill": 0.9, "focus": 0.5, "pitch": 9, "anim": "Walk", "t": 0.3}, ...]}]}
## Each shot writes <out>_<name>.png. "fill" is the share of the view height the model takes (the bay uses 0.9);
## larger values zoom in on the point at "focus" (fraction of the model height). A shot with "times": [..] instead
## of "t" writes <out>_<name>_<k>.png per time (filmstrips, clips). --mission-dust=<0..1> / --snow=<0..1> set the
## v2 shader's environment layer.

var _job := {}
var _vp: SubViewport
var _studio: MechStage.Studio


func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	_job = JSON.parse_string(FileAccess.get_file_as_string(args.get("job", "")))
	if _job == null:
		push_error("art_gallery: no --job")
		get_tree().quit(1)
		return
	var sz: Array = _job.get("size", [900, 900])
	_vp = SubViewport.new()
	_vp.size = Vector2i(int(sz[0]), int(sz[1]))
	_vp.own_world_3d = true
	_vp.transparent_bg = bool(_job.get("transparent", false))
	_vp.msaa_3d = Viewport.MSAA_4X
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	_studio = MechStage.Studio.new(_vp)
	if not _vp.transparent_bg:
		var we: WorldEnvironment = _vp.find_children("*", "WorldEnvironment", true, false)[0]
		we.environment.background_color = Color(_job.get("bg", "#2b2f36"))
	if args.has("mission-dust"):
		MechPaint.env_dust = float(args["mission-dust"])
	if args.has("snow"):
		MechPaint.env_snow = float(args["snow"])
	_run.call_deferred()


func _shot(model: Node3D, s: Dictionary) -> void:
	_studio.yaw = float(s.get("yaw", -22.0))
	_studio.apply_yaw()
	var aabb := _studio.aabb
	var h := aabb.size.y
	var w := maxf(aabb.size.x, aabb.size.z)
	var cam := _studio.cam
	var half_v := deg_to_rad(cam.fov) * 0.5
	var fill := float(s.get("fill", 0.9))
	var aspect := float(_vp.size.x) / float(_vp.size.y)
	var span := maxf(h / fill, w / fill / maxf(0.2, aspect))
	var dist := span * 0.5 / tan(half_v) + w * 0.5
	var c := aabb.get_center().rotated(Vector3.UP, deg_to_rad(_studio.yaw))
	var centre := Vector3(c.x, aabb.position.y + h * float(s.get("focus", 0.5)), c.z)
	var lift := deg_to_rad(float(s.get("pitch", 9.0)))
	cam.transform = Transform3D(Basis(), centre + Vector3(0, sin(lift), cos(lift)) * dist).looking_at(centre, Vector3.UP)


func _run() -> void:
	for item in _job["items"]:
		var path := String(item["path"])
		if not ResourceLoader.exists(path):
			push_warning("art_gallery: missing %s" % path)
			continue
		_studio.clear()
		var model: Node3D = (load(path) as PackedScene).instantiate()
		_studio.model = model
		_studio.pivot.add_child(model)
		if path.begins_with("res://assets/v2/objects/"):
			ArtV2.dress_object(model, path.get_file().get_basename())
		var paint: Array = item.get("paint", [])
		if item.has("scheme"):  # "player" (optionally with "pattern"), a faction scheme name ("steiner", "liao"...)
			# "player" is the default player scheme (reviews must not depend on what the tester saved); "player_saved" the saved one
			var nm := String(item["scheme"])
			var sch := PaintScheme.player() if nm == "player_saved" else PaintScheme.named("player_default" if nm == "player" else nm)
			if item.has("pattern"):
				sch["pattern"] = String(item["pattern"])
			MechPaint.apply_scheme(model, String(item.get("paint_name", "")), sch, String(item.get("folder", "mechs")))
			paint = []
		if paint.size() == 3:
			MechPaint.apply_scheme(model, String(item.get("paint_name", "")), PaintScheme.for_triple(paint),
				String(item.get("folder", "mechs")))
		var player: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
		_studio.aabb = MechStage.Studio._bounds(model)
		if String(item.get("folder", "mechs")) != "mechs":
			_studio.aabb = _mesh_bounds(model, _studio.aabb)  # rigid rigs: bones say little about the hull
		var r := maxf(_studio.aabb.size.x, _studio.aabb.size.z) * 1.1
		_studio.shadow.scale = Vector3(r, 1, r)
		_studio.shadow.position = Vector3(_studio.aabb.get_center().x, 0.02, _studio.aabb.get_center().z)
		for s in item["shots"]:
			var times: Array = s.get("times", [s.get("t", 0.0)])
			for k in times.size():
				if player:
					var anim := String(s.get("anim", "Idle"))
					if player.has_animation(anim):
						player.play(anim)
						player.seek(float(times[k]), true)
						player.pause()
				_shot(model, s)
				for i in 3:
					await RenderingServer.frame_post_draw
				var img := _vp.get_texture().get_image()
				var suffix: String = String(s.get("name", "a")) + ("_%03d" % k if s.has("times") else "")
				img.save_png("%s_%s.png" % [item["out"], suffix])
	get_tree().quit()


## Union of the meshes' AABBs through their node transforms (skins ignored: vehicle rigs bind at rest).
static func _mesh_bounds(root: Node3D, fallback: AABB) -> AABB:
	var box := AABB()
	var first := true
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var xf := Transform3D.IDENTITY
		var n: Node = mi
		while n and n != root:
			if n is Node3D:
				xf = (n as Node3D).transform * xf
			n = n.get_parent()
		var b: AABB = xf * (mi as MeshInstance3D).get_aabb()
		box = b if first else box.merge(b)
		first = false
	if first:
		return fallback
	box.size.y += minf(box.position.y, 0.0)
	box.position.y = minf(box.position.y, 0.0)
	return box
