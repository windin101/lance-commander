extends GdUnitTestSuite
## The mission briefing (HUD style): objectives primary first and numbered as on the map,
## the drop zone and intel from the mission file, selection by list or map with the
## original's 3-second cycling, and the buttons each flow gets.

var _camp: Campaign
var _current := ""


func before_test() -> void:
	_camp = Flow.campaign
	_current = Flow.current
	Flow.campaign = Campaign.create(GameData)


func after_test() -> void:
	Flow.campaign = _camp
	Flow.current = _current


func _screen(mission: String) -> BriefingScreen:
	Flow.current = mission
	var b: BriefingScreen = auto_free(load("res://scenes/briefing.tscn").instantiate())
	add_child(b)
	return b


func test_mission_data_for_the_briefing() -> void:
	var b := MissionBrief.load_mission(GameData, "mc2_02")
	assert_float(b.drop_limit).is_equal(170.0)
	assert_int(b.support_rp).is_equal(6000)
	assert_object(b.drop_zone).is_not_null()
	assert_str(b.weather()).is_equal("Clear")
	assert_array(b.support).contains(["Air strike", "Artillery"])
	var o: Dictionary = b.visible_objectives()[0]
	assert_int(o["reward"]).is_equal(4500)
	assert_str(o["model"]).is_equal("RPBuilding")
	assert_str(MissionBrief.load_mission(GameData, "mc2_10").weather()).is_equal("Rain")


func test_logistics_briefing_numbers_selects_and_cycles() -> void:
	MechBay.dev_sample(Flow.campaign)
	var s := _screen("mc2_02")
	var primaries: Array = s.numbered.filter(func(e): return e[1]["primary"])
	assert_int(s.numbered.size()).is_equal(s.brief.visible_objectives().size())
	for i in primaries.size():
		assert_bool(s.numbered[i][1]["primary"]).is_true()  # primaries first, numbered 1..n
	assert_int(s.map.numbered.size()).is_equal(s.numbered.size())
	assert_int(s.selected).is_equal(1)
	assert_str(s.target_label.text).contains("Target 1")  # the RP building's model
	# the original's cycling, until the player picks one
	s._process(BriefingScreen.CYCLE_S + 0.1)
	assert_int(s.selected).is_equal(2)
	s.select_objective(3, true)
	s._process(BriefingScreen.CYCLE_S + 0.1)
	assert_int(s.selected).is_equal(3)
	assert_int(s.map.selected).is_equal(3)
	# Mech Bay and Launch: the sample lance is ready (pilots, 140 of 170 t)
	assert_object(s.bay_button).is_not_null()
	assert_bool(s.launch_button.disabled).is_false()
	Flow.campaign.withdraw(Flow.campaign.deployed()[0])
	Flow.campaign.deployed()[0]["pilot"] = ""
	var s2 := _screen("mc2_02")
	assert_bool(s2.launch_button.disabled).is_true()
	assert_str(s2.launch_note.text).contains("pilot")


func test_quick_start_mission_launches_from_the_briefing() -> void:
	var s := _screen("mc2_01")  # no logistics: the mission's own lance
	assert_object(s.bay_button).is_null()
	assert_bool(s.launch_button.disabled).is_false()
	assert_str(s.launch_button.text).is_equal("LAUNCH MISSION")
