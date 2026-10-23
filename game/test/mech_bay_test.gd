extends GdUnitTestSuite
## The Mech Bay's market (Buy 'Mechs): offers replace the roster, a selected offer fills the
## detail panel and the stage, Buy says where the 'Mech goes or why it can't be bought.

var _camp: Campaign
var _current := ""
var _lab_id := -1
var _save := ""


func before_test() -> void:
	_camp = Flow.campaign
	_current = Flow.current
	_lab_id = Flow.lab_mech_id
	_save = Flow.save_path
	Flow.save_path = "user://test_mech_bay_campaign.json"
	Flow.campaign = Campaign.create(GameData)
	Flow.current = MechBay.dev_sample(Flow.campaign)
	Flow.lab_mech_id = -1


func after_test() -> void:
	Flow.campaign = _camp
	Flow.current = _current
	Flow.lab_mech_id = _lab_id
	Flow.save_path = _save
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://test_mech_bay_campaign.json"))


func _offer(bay: MechBay, chassis: String) -> Dictionary:
	for o in bay.camp.purchasable(bay.mission):
		if o["chassis"] == chassis:
			return o
	return {}


func test_market_selection_affordability_and_destination() -> void:
	var bay: MechBay = auto_free(load("res://scenes/mech_bay.tscn").instantiate())
	add_child(bay)
	bay._open_buy()
	assert_str(bay.mode).is_equal("market")
	assert_bool(bay._market_panel.visible and not bay._roster_panel.visible).is_true()
	assert_bool(bay.offer.is_empty()).is_false()  # the cheapest is selected
	# A werewolf fits the 30 t left: it would deploy.
	bay.select_offer(_offer(bay, "werewolf"))
	assert_str(bay._offer_title.text).is_equal("Razorback Prime")
	assert_str(bay._plate_name.text).is_equal("Werewolf")
	assert_bool(bay.buy_button.disabled).is_false()
	assert_str(bay.buy_note.text).contains("Joins the lance")
	# A bushwacker would not: reserve, and the note says why.
	bay.select_offer(_offer(bay, "bushwacker"))
	assert_str(bay.buy_note.text).contains("reserve")
	assert_str(bay.buy_note.text).contains("drop weight")
	var m := bay.buy_offer()
	assert_int(int(m["slot"])).is_equal(0)
	assert_int(bay.camp.mechs.size()).is_equal(5)
	# Too poor: Buy is off and says so.
	bay.camp.c_bills = 1000
	bay.select_offer(_offer(bay, "werewolf"))
	assert_bool(bay.buy_button.disabled).is_true()
	assert_str(bay.buy_note.text).contains("Not enough C-Bills")
	bay._close_market()
	assert_bool(bay._roster_panel.visible).is_true()


func test_personnel_screen_resume_and_assignment() -> void:
	MechBay.dev_history(Flow.campaign)
	var bay: MechBay = auto_free(load("res://scenes/mech_bay.tscn").instantiate())
	add_child(bay)
	bay._open_pilots()
	assert_str(bay.mode).is_equal("pilots")
	assert_bool(bay._pilot_panel.visible and bay._resume_panel.visible and not bay._roster_panel.visible).is_true()
	assert_bool(bay.stage.visible).is_false()
	assert_str(bay.pilot).is_equal("pmwhacksaw")  # assigned pilots first, by slot
	assert_str(bay._resume_title.text).is_equal("Hacksaw")
	assert_bool(bay.unassign_button.disabled).is_false()
	assert_str(MechBay.bio("pmwhacksaw")).is_not_empty()
	# An available pilot: Assign opens the 'Mech list; picking the reserve Werewolf deploys it.
	bay.select_pilot("pmwcobra")
	assert_bool(bay.unassign_button.disabled).is_true()
	assert_bool(bay.assign_button.disabled).is_false()
	var wolf: Dictionary = bay.camp.mechs[3]
	assert_bool(bay.assign_selected(wolf)).is_true()
	assert_str(String(wolf["pilot"])).is_equal("pmwcobra")
	assert_int(int(wolf["slot"])).is_equal(4)
	# From the hangar's Assign pilot: the résumé offers that 'Mech and returns to the hangar.
	bay._close_personnel()
	bay._select(int(bay.camp.mechs[0]["id"]))
	bay._open_assign()
	assert_int(bay.assign_to).is_equal(int(bay.camp.mechs[0]["id"]))
	assert_str(bay.assign_note.text).contains("Already in this")
	bay.select_pilot("pmwchopper")
	assert_str(bay.assign_button.text).contains("BUSHWACKER")
	bay._assign_pressed()
	assert_str(String(bay.camp.mechs[0]["pilot"])).is_equal("pmwchopper")
	assert_str(bay.mode).is_equal("hangar")
