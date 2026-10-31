extends Node
## Every wall/gate/post placement of a mission, as the real ObjectsView holds it: node present, visible, mesh surfaces, AABB.
## godot --headless --path game res://tools/wall_nodes.tscn -- --mission=mc2_12
func _ready() -> void:
	var m := "mc2_12"
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--mission="):
			m = a.split("=")[1]
	var camp := Campaign.create(GameData)
	camp.add_mech("atlas", 0, "pmwhacksaw", 1)
	var view: Node = load("res://scenes/mission_view.tscn").instantiate()
	view.mission = m
	view.force = camp.force()
	add_child(view)
	await get_tree().create_timer(1.0).timeout
	var ov: ObjectsView = view.objects_view
	var bad := 0
	var total := 0
	var kinds := {}
	for index in ov.nodes:
		var app: String = ov._appearance.get(index, "")
		if not (app.begins_with("s_") or app.begins_with("l_") or app.begins_with("d_")) or not (app.contains("wall") or app.contains("gate") or app.contains("post")):
			continue
		total += 1
		var n: Node3D = ov.nodes[index]
		var l0 := n.find_child("lod0", true, false) as MeshInstance3D
		var l1 := n.find_child("lod1", true, false) as MeshInstance3D
		var why := ""
		if not n.visible: why += "hidden "
		if l0 == null or l1 == null: why += "nolod "
		else:
			if l0.mesh.get_surface_count() == 0 or l1.mesh.get_surface_count() == 0: why += "nosurf "
			var b0 := l0.mesh.get_aabb(); var b1 := l1.mesh.get_aabb()
			if b0.size.z < 20.0 and not app.contains("post"): why += "short0 "
			if b1.size.z < 20.0 and not app.contains("post"): why += "short1 "
			if l0.visibility_range_end != 80.0 or l1.visibility_range_begin != 80.0: why += "norange "
		kinds[app] = kinds.get(app, 0) + 1
		if why != "":
			bad += 1
			print("BAD ", index, " ", app, " ", why)
	print("WALLNODES ", m, " total ", total, " bad ", bad, " ", kinds)
	get_tree().quit()
