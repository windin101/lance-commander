extends GdUnitTestSuite
## Converted mech models: animations present, sidecar matches the chassis data.

const SLICE := {"bushwacker": "bushwacker", "werewolf": "werewolf", "starslayer": "starslayer", "urbanmech": "urbanmech"}


func test_models_load_with_gesture_animations() -> void:
	for m in SLICE:
		var scene: PackedScene = load("res://assets/mechs/%s.glb" % m)
		assert_object(scene).is_not_null()
		var root := scene.instantiate()
		var player: AnimationPlayer = root.find_child("AnimationPlayer", true, false)
		assert_object(player).is_not_null()
		for anim in ["Walk", "Run", "Idle", "FallForward"]:
			assert_bool(player.has_animation(anim)).override_failure_message("%s lacks %s" % [m, anim]).is_true()
		root.free()


func test_sidecar_run_speed_matches_chassis_csv() -> void:
	for m in SLICE:
		var side: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/mechs/%s.json" % m))
		var run: Dictionary = side["gestures"][7]
		assert_str(run["id"]).is_equal("run")
		var chassis: Dictionary = GameData.chassis[SLICE[m]]
		assert_float(float(run["end_velocity"])).override_failure_message(m).is_equal(float(chassis["max_run_speed"]))
		assert_int(side["weapon_nodes"].size()).is_greater(0)
