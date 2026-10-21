class_name MechStage
extends SubViewportContainer
## A 'Mech's HD model, live in its own small 3D world (SubViewport, transparent background)
## for the Mech Bay and Mech Lab: painted with the mission's player colours, idling, lit
## with a key light and a cyan rim to sit on the HUD panels. Drag to turn it.
## MechStage.Thumbs renders still thumbnails (cached per chassis and paint).

var studio: Studio
var vp: SubViewport
var spin := 0.0  # degrees per second of slow turntable rotation
var _dragging := false


func _init() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	vp = SubViewport.new()
	vp.own_world_3d = true
	vp.transparent_bg = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	add_child(vp)
	studio = Studio.new(vp)
	resized.connect(func(): studio.frame(_aspect()))


func _aspect() -> float:
	return size.x / maxf(1.0, size.y)


func show_mech(chassis: String, paint: Array, yaw_deg := -28.0) -> void:
	studio.yaw = yaw_deg
	studio.show(chassis, paint)
	studio.frame(_aspect())


func _process(delta: float) -> void:
	if spin != 0.0 and not _dragging:
		studio.yaw += spin * delta
		studio.apply_yaw()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_dragging = event.pressed
		accept_event()
	elif event is InputEventMouseMotion and _dragging:
		studio.yaw += event.relative.x * 0.5
		studio.apply_yaw()
		accept_event()


## The 3D content of one SubViewport: lights, a soft floor shadow, the model on a pivot and
## a camera framed on the model's bounds.
class Studio:
	extends RefCounted
	var vp: SubViewport
	var pivot: Node3D
	var cam: Camera3D
	var model: Node3D
	var aabb := AABB(Vector3(-3, 0, -2), Vector3(6, 8, 4))
	var yaw := -28.0
	var fill := 0.9  # share of the view height the 'Mech takes
	var shadow: MeshInstance3D

	func _init(viewport: SubViewport) -> void:
		vp = viewport
		var root := Node3D.new()
		vp.add_child(root)
		var env := Environment.new()
		env.background_mode = Environment.BG_CLEAR_COLOR
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color(0.42, 0.47, 0.52)
		env.ambient_light_energy = 0.65
		env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		var we := WorldEnvironment.new()
		we.environment = env
		root.add_child(we)
		var key := DirectionalLight3D.new()
		key.rotation_degrees = Vector3(-38, -35, 0)
		key.light_energy = 1.35
		root.add_child(key)
		var fill_light := DirectionalLight3D.new()
		fill_light.rotation_degrees = Vector3(-15, 120, 0)
		fill_light.light_energy = 0.35
		fill_light.light_color = Color(0.7, 0.8, 0.9)
		root.add_child(fill_light)
		var rim := DirectionalLight3D.new()
		rim.rotation_degrees = Vector3(-20, 180 + 25, 0)
		rim.light_energy = 1.1
		rim.light_color = UiStyle.HUD_EDGE
		root.add_child(rim)
		shadow = MeshInstance3D.new()
		var plane := PlaneMesh.new()
		plane.size = Vector2(1, 1)
		shadow.mesh = plane
		var sm := StandardMaterial3D.new()
		sm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		var g := Gradient.new()
		g.set_color(0, Color(0, 0, 0, 0.75))
		g.set_color(1, Color(0, 0, 0, 0))
		var gt := GradientTexture2D.new()
		gt.gradient = g
		gt.fill = GradientTexture2D.FILL_RADIAL
		gt.fill_from = Vector2(0.5, 0.5)
		gt.fill_to = Vector2(1.0, 0.5)
		sm.albedo_texture = gt
		shadow.material_override = sm
		root.add_child(shadow)
		pivot = Node3D.new()
		root.add_child(pivot)
		cam = Camera3D.new()
		cam.fov = 26.0
		cam.near = 0.1
		cam.far = 400.0
		root.add_child(cam)
		cam.current = true

	func show(chassis: String, paint: Array) -> void:
		if model:
			pivot.remove_child(model)
			model.queue_free()
			model = null
		var path := "res://assets/mechs/%s_hd.glb" % chassis
		var paint_name := chassis + "_hd"
		if not ResourceLoader.exists(path):
			path = "res://assets/mechs/%s.glb" % chassis
			paint_name = chassis
		if not ResourceLoader.exists(path):
			return
		model = (load(path) as PackedScene).instantiate()
		pivot.add_child(model)
		if paint.size() == 3:
			MechPaint.apply(model, paint_name, MechPaint.argb(int(paint[0])), MechPaint.argb(int(paint[1])), MechPaint.argb(int(paint[2])))
		var player: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
		if player and player.has_animation("Idle"):
			player.get_animation("Idle").loop_mode = Animation.LOOP_LINEAR
			player.play("Idle")
		aabb = _bounds(model)
		var r := maxf(aabb.size.x, aabb.size.z) * 1.1
		shadow.scale = Vector3(r, 1, r)
		shadow.position = Vector3(aabb.get_center().x, 0.02, aabb.get_center().z)
		apply_yaw()

	func apply_yaw() -> void:
		pivot.rotation_degrees.y = yaw

	## Fit the 'Mech's height (or width, for a narrow view) to the view, feet near the bottom.
	func frame(aspect: float) -> void:
		var h := aabb.size.y
		var w := maxf(aabb.size.x, aabb.size.z)
		var half_v := deg_to_rad(cam.fov) * 0.5
		var need_h := h / fill
		var need_w := w / fill / maxf(0.2, aspect)
		var span := maxf(need_h, need_w)
		var dist := span * 0.5 / tan(half_v) + w * 0.5
		var centre := Vector3(0, aabb.position.y + h * 0.5, 0)
		var lift := deg_to_rad(9.0)
		cam.transform = Transform3D(Basis(), centre + Vector3(0, sin(lift), cos(lift)) * dist).looking_at(centre, Vector3.UP)

	## The model's extent from its skeleton (skinned meshes' own AABBs sit in bind-pose
	## space, offset from where the 'Mech stands): bones plus a margin, feet on the floor.
	static func _bounds(root: Node3D) -> AABB:
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		for s in root.find_children("*", "Skeleton3D", true, false):
			var sk := s as Skeleton3D
			var xf := Transform3D.IDENTITY
			var n: Node = sk
			while n and n != root:
				if n is Node3D:
					xf = (n as Node3D).transform * xf
				n = n.get_parent()
			for b in sk.get_bone_count():
				var p: Vector3 = xf * sk.get_bone_global_pose(b).origin
				lo = lo.min(p)
				hi = hi.max(p)
		if lo.x == INF:
			for mi in root.find_children("*", "MeshInstance3D", true, false):
				var b: AABB = (mi as MeshInstance3D).get_aabb()
				lo = lo.min(b.position)
				hi = hi.max(b.end)
		if lo.x == INF:
			return AABB(Vector3(-3, 0, -2), Vector3(6, 8, 4))
		var h := hi.y * 1.12
		var pad := h * 0.12
		return AABB(Vector3(lo.x - pad, 0.0, lo.z - pad), Vector3(hi.x - lo.x + 2.0 * pad, h, hi.z - lo.z + 2.0 * pad))


## Still thumbnails of 'Mechs, rendered one at a time in a hidden SubViewport and cached
## by chassis and paint for the session.
class Thumbs:
	extends Node
	static var cache := {}
	var _queue: Array = []  # [key, chassis, paint, [callbacks]]
	var _vp: SubViewport
	var _studio: Studio
	var px := 192

	func request(chassis: String, paint: Array, cb: Callable) -> void:
		var key := "%s|%s" % [chassis, str(paint)]
		if cache.has(key):
			cb.call(cache[key])
			return
		for q in _queue:
			if q[0] == key:
				q[3].append(cb)
				return
		_queue.append([key, chassis, paint, [cb]])

	var _frames := -1  # frames left before the current model's shot is taken

	## One model at a time: show it, let three frames render, read the image back. Driven
	## by _process so nothing is left waiting when the screen goes.
	func _process(_delta: float) -> void:
		if _frames < 0:
			if _queue.is_empty():
				return
			if _vp == null:
				_vp = SubViewport.new()
				_vp.size = Vector2i(px, px)
				_vp.own_world_3d = true
				_vp.transparent_bg = true
				_vp.msaa_3d = Viewport.MSAA_4X
				_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
				add_child(_vp)
				_studio = Studio.new(_vp)
				_studio.fill = 0.96
				_studio.yaw = -28.0
				_studio.shadow.visible = false
			_studio.show(_queue[0][1], _queue[0][2])
			_studio.frame(1.0)
			_frames = 3
			return
		_frames -= 1
		if _frames > 0:
			return
		_frames = -1
		var q: Array = _queue.pop_front()
		var img := _vp.get_texture().get_image()
		if img == null or img.is_empty():
			return
		var tex := ImageTexture.create_from_image(img)
		cache[q[0]] = tex
		for cb in q[3]:
			if cb.is_valid():
				cb.call(tex)
