extends GdUnitTestSuite
## Mission flow: campaign order and progress, the briefing and debrief data, and the
## screens building without errors.

const SAVE := "user://flow_test_campaign.json"

var flow: Node


func before_test() -> void:
	flow = load("res://scripts/flow/flow.gd").new()
	flow.save_path = SAVE
	if FileAccess.file_exists(SAVE):
		DirAccess.remove_absolute(SAVE)
	flow.load_campaign()


func after_test() -> void:
	flow.free()


func test_campaign_order() -> void:
	assert_int(flow.missions.size()).is_greater_equal(24)
	assert_str(flow.missions[0]["name"]).is_equal("mc2_01")
	assert_str(flow.missions[0]["pre_video"]).is_equal("cinema1")
	assert_str(flow.next_after("mc2_01")).is_equal("mc2_02")
	assert_str(flow.current).is_equal("mc2_01")
	assert_bool(flow.is_available("mc2_01")).is_true()


func test_a_win_advances_and_persists() -> void:
	flow.record({"mission": "mc2_01", "won": true, "time": 200.0})
	assert_str(flow.current).is_equal("mc2_02")
	var again: Node = load("res://scripts/flow/flow.gd").new()
	again.save_path = SAVE
	again.load_campaign()
	again.load_progress()
	assert_str(again.current).is_equal("mc2_02")
	assert_bool(again.completed.has("mc2_01")).is_true()
	again.free()


func test_a_loss_stays_on_the_mission() -> void:
	flow.record({"mission": "mc2_01", "won": false})
	assert_str(flow.current).is_equal("mc2_01")
	assert_dict(flow.completed).is_empty()


func test_briefing_data() -> void:
	var b := MissionBrief.load_mission(GameData, "mc2_01")
	assert_str(b.title).is_equal("Scouting Patrol")
	assert_str(b.blurb).contains("Tactical Officer Notes")
	assert_int(b.lance.size()).is_equal(3)
	assert_str(b.lance[0]["chassis"]).is_equal("Werewolf")
	assert_str(b.lance[0]["pilot"]).is_equal("Flash")
	var vis := b.visible_objectives()
	assert_int(vis.size()).is_greater_equal(6)
	assert_object(vis[0]["marker"]).is_not_null()
	assert_float(b.map_half_m).is_equal_approx(1280.0, 0.01)
	assert_bool(MissionBrief.load_mission(GameData, "mc2_24").available).is_true()
	assert_bool(MissionBrief.load_mission(GameData, "mc2_99").available).is_false()


func test_report_counts_kills_and_lance_state() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01", 2)
	var enemy: SimUnit = sm.world.units.filter(func(u): return u.team != 0 and u.is_mover())[0]
	enemy.status = SimUnit.Status.DESTROYED
	var r := MissionReport.from_sim(sm, "Scouting Patrol", GameData)
	assert_bool(r["won"]).is_false()
	assert_int(r["lance"].size()).is_equal(3)
	assert_str(r["lance"][0]["state"]).is_equal("Operational")
	assert_int(r["kills"][0]["count"]).is_equal(1)


func test_screens_build() -> void:
	Flow.current = "mc2_01"
	var brief: Control = load("res://scenes/briefing.tscn").instantiate()
	add_child(brief)
	await get_tree().process_frame
	assert_bool(brief.launch_button.disabled).is_false()
	brief.queue_free()
	Flow.last_report = {"mission": "mc2_01", "title": "Scouting Patrol", "won": true, "time": 61.0,
		"objectives": [{"title": "Investigate", "primary": true, "complete": true}],
		"lance": [{"name": "Werewolf", "pilot": "Flash", "state": "Damaged", "armour": 55}],
		"kills": [{"name": "Harasser", "count": 2}], "losses": 0}
	var de: Control = load("res://scenes/debrief.tscn").instantiate()
	add_child(de)
	await get_tree().process_frame
	assert_object(de.continue_button).is_not_null()
	de.queue_free()


func test_mission_end_offers_the_debrief_and_esc_pauses() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var esc := InputEventKey.new()
	esc.keycode = KEY_ESCAPE
	esc.pressed = true
	view.pause_menu._unhandled_input(esc)
	assert_bool(get_tree().paused).is_true()
	view.pause_menu._unhandled_input(esc)
	assert_bool(get_tree().paused).is_false()
	view.sm.objectives.result = SimObjectives.Result.WON
	view._process(0.0)
	view.world.time += 3.5
	view._process(0.0)
	assert_bool(view.pause_menu.ended).is_true()
	assert_bool(view.pause_menu.panel.visible).is_true()
	assert_str(view.pause_menu.title.text).is_equal("MISSION SUCCESSFUL")
	var r: Dictionary = view.report()
	assert_bool(r["won"]).is_true()
	assert_int(r["lance"].size()).is_equal(3)
	assert_str(r["title"]).is_equal("Scouting Patrol")
	view.queue_free()
