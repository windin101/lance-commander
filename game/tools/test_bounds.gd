extends Node
## Same bounds the building test uses (nodes inside a scene tree). godot --headless --path game res://tools/test_bounds.tscn -- app ...
func _ready() -> void:
	for app in OS.get_cmdline_user_args():
		var orig: Node3D = (load("res://assets/objects/%s.glb" % app) as PackedScene).instantiate()
		add_child(orig)
		var out := AABB(); var first := true
		for m in orig.find_children("*", "MeshInstance3D", true, false):
			var mi := m as MeshInstance3D
			if mi.mesh == null or mi.name.to_lower().begins_with("litwin"): continue
			var bb: AABB = (orig.global_transform.affine_inverse() * mi.global_transform) * mi.mesh.get_aabb()
			out = bb if first else out.merge(bb); first = false
		print("TB %s %.1f %.1f %.1f %.1f %.1f %.1f" % [app, out.position.x, out.end.x, out.position.z, out.end.z, out.position.y, out.end.y])
	get_tree().quit()
