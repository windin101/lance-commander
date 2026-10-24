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
	if args.has("cam-view"):  # --cam-view=yaw,pitch,distance after the view has set itself up (scenery shots)
		_cam_view.call_deferred(view, String(args["cam-view"]).split(","))


func _cam_view(view: Node, v: PackedStringArray) -> void:
	if view.camera is RtsCamera and v.size() >= 3:
		var cam := view.camera as RtsCamera
		cam.limits = false
		if v[0] != "-":
			cam.yaw_deg = float(v[0])
		cam.pitch_deg = float(v[1])
		cam.distance = float(v[2])


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
