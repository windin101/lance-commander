extends Node
## Dev: a mission played with a campaign force instead of the mission file's own lance (whose
## pilots are multiplayer placeholders), for screenshots. User args, besides the mission view's own
## (--mission, --demo, --focus...): --lance=<chassis>:<pilot profile>,... (default a mixed lance of
## campaign pilots); --fort puts the lance 170 m from the enemy's densest turret cluster, orders it in
## and runs the sim until the turrets have fired (a turret fort fight); --cam-view=yaw,pitch,distance.

const DEFAULT_LANCE := "atlas:pmwhacksaw,madcat:pmwlongshot,bushwacker:pmwflash,catapult:pmwjinx"


func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var camp := Campaign.create(GameData)
	var slot := 1
	for entry in String(args.get("lance", DEFAULT_LANCE)).split(","):
		var bits := entry.split(":")
		if GameData.chassis.has(bits[0]):
			camp.add_mech(bits[0], 0, bits[1] if bits.size() > 1 else "", slot)
			slot += 1
	var view: Node = load("res://scenes/mission_view.tscn").instantiate()
	view.mission = String(args.get("mission", "mc2_01"))
	view.force = camp.force()
	view.name = "MissionView"
	add_child(view)
	if args.has("fort"):
		_fort.call_deferred(view)
	if args.has("wreck"):  # --wreck=<model>: destroy the first unit of that model and frame it (wreck art checks)
		_wreck.call_deferred(view, String(args["wreck"]))
	_hide_units = args.has("hide-units")
	_mask_units = args.has("mask-units")
	if args.has("focus-lance"):  # --focus-lance[=<dist>]: frame the player's lance (unit brightness checks)
		_focus_lance.call_deferred(view)
	if args.has("focus-unit"):  # --focus-unit=<model>: frame the first live unit of that model (art checks on civilians and vehicles)
		_focus_unit.call_deferred(view, String(args["focus-unit"]))
	if args.has("night"):  # --night: day map shown as night for glow checks (night lamp strengths, sun and ambient cut): BuildingV3.set_night(true)
		_night.call_deferred(view)
	if args.has("turret"):  # --turret=<appearance>[,<yaw offset deg>]: park the first such map turret, turned off its placed facing (turret art checks)
		_turret.call_deferred(view, String(args["turret"]).split(","))
	if args.has("cam-view"):  # --cam-view=yaw,pitch,distance after the view has set itself up (scenery shots)
		_cam_view.call_deferred(view, String(args["cam-view"]).split(","))


func _wreck(view: Node, model: String) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	for u in view.world.units:
		if u.model == model and view.views.has(u.id):
			u.status = SimUnit.Status.DESTROYED
			view.views[u.id].visible = true
			view.views[u.id].sync(1.0)
			if view.camera is RtsCamera:
				(view.camera as RtsCamera).limits = false
				(view.camera as RtsCamera).following = null   # the camera follows the lance by default
				if view.compass:
					view.compass.enabled = false   # the ground compass arrow at the focus covers the wreck
				(view.camera as RtsCamera).focus = Vector3(u.position.x, view.world.map.height_at(u.position), -u.position.y)
			return


var _hide_units := false
var _mask_units := false
var _mask_mat: StandardMaterial3D


func _process(_dt: float) -> void:
	if _mask_units:  # --mask-units: every unit mesh flat unshaded magenta, the exact silhouette for unit brightness masks
		var view2 := get_node_or_null("MissionView")
		if view2 and "views" in view2:
			if _mask_mat == null:
				_mask_mat = StandardMaterial3D.new()
				_mask_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
				_mask_mat.albedo_color = Color(1, 0, 1)
			for v in view2.views.values():
				for mi in (v as Node).find_children("*", "MeshInstance3D", true, false):
					if mi.get_parent() != null and not String(mi.name).begins_with("Ring"):
						(mi as MeshInstance3D).material_override = _mask_mat
	if _hide_units:  # --hide-units: the background-only frame for unit brightness masks (tools/art/v3/unit_lum.py)
		var view := get_node_or_null("MissionView")
		if view and "views" in view:
			for v in view.views.values():
				v.visible = false


func _focus_lance(view: Node) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var pos := Vector2.ZERO
	var n := 0
	for u in view.world.units:
		if u.is_mover() and u.is_player and not u.is_destroyed():
			if n == 0:
				pos = u.position  # the first player unit (a lance spread over a map has no useful mean)
			n += 1
	if n == 0 or not (view.camera is RtsCamera):
		return
	var cam := view.camera as RtsCamera
	cam.limits = false
	cam.following = null
	if view.compass:
		view.compass.enabled = false
	cam.focus = Vector3(pos.x, view.world.map.height_at(pos), -pos.y)


func _focus_unit(view: Node, model: String) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	for u in view.world.units:
		if u.model == model and not u.is_destroyed() and view.camera is RtsCamera:
			var cam := view.camera as RtsCamera
			cam.limits = false
			cam.following = null
			if view.compass:
				view.compass.enabled = false
			cam.focus = Vector3(u.position.x, view.world.map.height_at(u.position), -u.position.y)
			return


func _night(view: Node) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	BuildingV3.set_night(true)
	for l in view.find_children("*", "DirectionalLight3D", true, false):
		(l as DirectionalLight3D).light_energy *= 0.08
	for we in view.find_children("*", "WorldEnvironment", true, false):
		var env: Environment = (we as WorldEnvironment).environment
		if env:
			env.ambient_light_energy *= 0.2
			env.background_energy_multiplier *= 0.15
			env.tonemap_exposure *= 0.8


func _turret(view: Node, v: PackedStringArray) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var pick: SimTurret = null
	for u in view.world.units:
		if u is SimTurret and view.objects_view._appearance.get(u.object_index, "") == v[0]:
			pick = u
			break
	if pick == null:  # not a turret (a control centre, a generator): frame the first placed object of that appearance
		for idx in view.objects_view._appearance:
			if view.objects_view._appearance[idx] == v[0] and view.objects_view.nodes.has(idx) and view.camera is RtsCamera:
				var cam0 := view.camera as RtsCamera
				cam0.limits = false
				cam0.following = null
				if view.compass:
					view.compass.enabled = false
				cam0.focus = view.objects_view.bounds(idx).get_center()
				return
		push_warning("force_mission: no map object of appearance %s" % v[0])
		return
	pick.active = false   # no scanning: the turret holds the pose it is given
	for fl in v.slice(2):  # flags in order: destroy | damaged | pop=<0..1>
		if fl == "destroy":
			view.objects_view.destroy(pick.object_index)
		elif fl == "damaged":
			view.objects_view.set_damage(pick.object_index, 0.6)
		elif fl.begins_with("pop="):
			view.objects_view._apply_pop(float(fl.substr(4)), pick.object_index)
	pick.turret_yaw = float(pick.facing) + (float(v[1]) if v.size() > 1 else 0.0)
	if view.camera is RtsCamera:
		var cam := view.camera as RtsCamera
		cam.limits = false
		cam.following = null
		if view.compass:
			view.compass.enabled = false
		cam.focus = Vector3(pick.position.x, view.world.map.height_at(pick.position), -pick.position.y)


func _cam_view(view: Node, v: PackedStringArray) -> void:
	if view.camera is RtsCamera and v.size() >= 3:
		var cam := view.camera as RtsCamera
		cam.limits = false
		cam.edge_scroll = false   # a mouse resting at the window edge pans the camera and the shot changes from run to run
		if v[0] != "-":
			cam.yaw_deg = float(v[0])
		cam.pitch_deg = float(v[1])
		cam.distance = float(v[2])
		if _hide_units and view.compass:
			view.compass.enabled = false   # terrain review shots: no ground compass arrow at the focus
		if v.size() >= 5:   # optional focus in sim metres (map centre = 0), for maps whose lance starts off the map
			cam.following = null   # else the camera drifts back to the lance and a shot depends on timing
			cam.focus = Vector3(float(v[3]), 0, -float(v[4]))


func _fort(view: Node) -> void:
	var w: SimWorld = view.world
	var team: int = view.sm.player_team
	var turrets: Array = w.units.filter(func(u): return u is SimTurret and u.team != team and u.team >= 0 and not u.is_destroyed())
	var lance: Array = w.units.filter(func(u): return u.team == team and u.commander == 0 and u is SimMech)
	if turrets.is_empty() or lance.is_empty():
		return
	var best: SimUnit = turrets[0]
	var most := 0
	for t in turrets:
		var n: int = turrets.filter(func(o): return o.position.distance_to(t.position) < 200.0).size()
		if n > most:
			most = n
			best = t
	var away: Vector2 = (lance[0].position - best.position).normalized()
	if away == Vector2.ZERO:
		away = Vector2(0, -1)
	for i in lance.size():
		var m: SimUnit = lance[i]
		m.position = w.map.nearest_walkable(best.position + away.rotated(0.25 * (i - lance.size() / 2.0)) * 170.0)
		m.prev_position = m.position
		w.order_attack(m, best)
	var shots := 0
	for i in 1500:
		view.sm.step()
		for e in w.events:
			if e["type"] == "shot" and turrets.any(func(t): return t.id == int(e["from"])):
				shots += 1
		view._consume_events(false)
		if shots >= 6:
			break
	if view.camera is RtsCamera:  # frame the fight: between the lance and the fort, looking at the fort
		var cam := view.camera as RtsCamera
		var mid: Vector2 = best.position.lerp(lance[0].position, 0.4)
		cam.pan_to(mid)
		cam.yaw_deg = rad_to_deg(atan2(-away.x, -away.y))
		cam.distance = cam.distance * 0.75
