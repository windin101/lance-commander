extends GdUnitTestSuite
## LANCE-19: the skinned-style v3 units (infantry, powered armour) keep the original's Walk and Run animations and have a mesh on
## every part, so MechView (which plays "Walk" from the model's AnimationPlayer for a non-SimMech unit) can animate them.

const DIR := "res://assets/v3/vehicles/"


func test_walkers_have_walk_run_and_meshes() -> void:
	for unit in ["infantry", "poweredarmor"]:
		if not ResourceLoader.exists(DIR + unit + ".glb"):
			continue
		var model: Node3D = (load(DIR + unit + ".glb") as PackedScene).instantiate()
		add_child(model)
		var player: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
		assert_object(player).is_not_null()
		assert_bool(player.has_animation("Walk")).is_true()
		assert_bool(player.has_animation("Run")).is_true()
		assert_bool(player.get_animation("Walk").length > 0.1).is_true()
		var meshes := model.find_children("*", "MeshInstance3D", true, false)
		assert_int(meshes.size()).is_greater(4)
		# VehicleRig must not claim an animated unit: its rig is built only for models with no Walk
		model.queue_free()
