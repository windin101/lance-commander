extends SceneTree
func _bb(path: String) -> AABB:
	var n: Node3D = (load(path) as PackedScene).instantiate(); root.add_child(n)
	var bb := AABB(); var first := true
	for m in n.find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		if mi.mesh == null or mi.name.to_lower().begins_with("litwin"): continue
		var b: AABB = (n.global_transform.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb()
		bb = b if first else bb.merge(b); first = false
	return bb
func _init() -> void:
	for pair in [["jeepprop","jeep"],["truckprop","truck"],["armoredcarprop","armoredcar"],["cargotruckprop","cargotruck"],["fueltruckprop","fueltruck"],["ordnancetruckprop","ordnancetruck"],["trooptransportprop","trooptransport"],["ambulanceprop","ambulance"],["dunebuggyprop","jeep"]]:
		var o := _bb("res://assets/objects/%s.glb" % pair[0]); var v := _bb("res://assets/v3/vehicles/%s.glb" % pair[1])
		print("PB %-18s prop x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f] | veh %-14s x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f]" % [pair[0], o.position.x, o.end.x, o.position.y, o.end.y, o.position.z, o.end.z, pair[1], v.position.x, v.end.x, v.position.y, v.end.y, v.position.z, v.end.z])
	quit()
