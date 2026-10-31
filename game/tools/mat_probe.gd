extends SceneTree
func _init() -> void:
	for n in ["pipegreen", "palepaint", "brick", "concrete"]:
		var m := BuildingV3.material(n)
		print("MAT ", n, " tint ", m.get_shader_parameter("base_tint"), " resolves ", BuildingV3.resolves(n))
	var ps: PackedScene = load("res://assets/v3/objects/cornerpipe.glb")
	var nd: Node3D = ps.instantiate()
	for mi in nd.find_children("*", "MeshInstance3D", true, false):
		for i in (mi as MeshInstance3D).mesh.get_surface_count():
			print("SURF ", mi.name, " ", (mi as MeshInstance3D).mesh.surface_get_material(i).resource_name)
	quit()
