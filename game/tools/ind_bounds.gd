extends SceneTree
func _aabb(n: Node) -> AABB:
	var out := AABB(); var first := true
	var list: Array = n.find_children("*", "MeshInstance3D", true, false)
	if n is MeshInstance3D: list.append(n)
	for m in list:
		var mi := m as MeshInstance3D
		if mi.mesh == null or mi.name.begins_with("LitWin"): continue
		var bb: AABB = mi.mesh.get_aabb() if mi == n else (n.global_transform.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb()
		out = bb if first else out.merge(bb); first = false
	return out
func _init() -> void:
	for app in "chemicalplant processingplant purificationplant wasteprocessor industrialplant industrialcomplex heavyindustrial factorysm factorymd factorylg powergenerator transformerstation valvestation relaystation straightpipe1 straightpipe2 straightpipe3 cornerpipe endpipe threewaypipe fourwaypipe crane gantry".split(" "):
		var o: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate(); root.add_child(o)
		var ob := _aabb(o)
		var n: Node3D = (load(BuildingV3.model_path(app)) as PackedScene).instantiate(); root.add_child(n)
		var b := _aabb(n.find_child("lod0", true, false)); var b1 := _aabb(n.find_child("lod1", true, false))
		print("IB %-18s dx0 %5.1f dx1 %5.1f dz0 %5.1f dz1 %5.1f dy0 %5.1f dy1 %5.1f | lod1 dx %4.1f %4.1f dz %4.1f %4.1f dy1 %4.1f" % [app,
			b.position.x - ob.position.x, b.end.x - ob.end.x, b.position.z - ob.position.z, b.end.z - ob.end.z, b.position.y - ob.position.y, b.end.y - ob.end.y,
			b1.position.x - ob.position.x, b1.end.x - ob.end.x, b1.position.z - ob.position.z, b1.end.z - ob.end.z, b1.end.y - ob.end.y])
	quit()
