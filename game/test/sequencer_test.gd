extends GdUnitTestSuite
## Mission sequencer: waits, videos (skipped when the retail files are absent), VO conditions.

var view: Node3D


func before_test() -> void:
	view = load("res://scenes/mission_view.tscn").instantiate()
	add_child(view)
	await get_tree().process_frame


func after_test() -> void:
	view.queue_free()


func _drive(seconds: float) -> void:
	for i in int(seconds / SimWorld.TICK):
		view.world.time += SimWorld.TICK
		view.sequencer._process(SimWorld.TICK)


func test_missing_videos_are_skipped_and_vo_follows() -> void:
	var seq: MissionSequencer = view.sequencer
	seq.videos = {}  # as on a machine without the retail disc
	seq._queue.clear()
	seq._wait_until = -1.0
	seq._busy = false
	seq.start("start")
	_drive(8.0)
	assert_bool(view.hud.comms.visible).is_false()
	assert_bool(seq._queue.is_empty()).is_true()  # waits passed, videos skipped, VO issued


func test_airfield_vo_dropped_if_objective_done() -> void:
	var seq: MissionSequencer = view.sequencer
	seq.videos = {}
	seq._queue.clear()
	seq._wait_until = -1.0
	seq._busy = false
	view.sm.objectives.objectives[0]["complete"] = true
	seq._queue.append({"vo": "tut_1cii", "unless_objective": 0})
	seq._process(0.1)
	assert_bool(seq._busy).is_false()
	assert_bool(seq._queue.is_empty()).is_true()


func test_sequences_configured() -> void:
	assert_array(view.sequencer.sequences.get("start", [])).is_not_empty()
	assert_array(view.sequencer.sequences.get("objective:8", [])).is_not_empty()
