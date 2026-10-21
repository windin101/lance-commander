extends GdUnitTestSuite
## The Mech Lab screen over a sample campaign: a selected part lights only the locations
## that can take it, a refused fit says why, fitting and removing keep the bill and stores
## right. (Confirm is Campaign.refit, covered in campaign_test.)

var _camp: Campaign
var _current := ""
var _lab_id := -1


func before_test() -> void:
	_camp = Flow.campaign
	_current = Flow.current
	_lab_id = Flow.lab_mech_id
	Flow.campaign = Campaign.create(GameData)
	Flow.current = MechBay.dev_sample(Flow.campaign)
	Flow.lab_mech_id = int(Flow.campaign.mechs[0]["id"])


func after_test() -> void:
	Flow.campaign = _camp
	Flow.current = _current
	Flow.lab_mech_id = _lab_id


func _lab() -> MechLab:
	var lab: MechLab = auto_free(load("res://scenes/mech_lab.tscn").instantiate())
	add_child(lab)
	return lab


func test_lab_fits_and_strips_parts() -> void:
	var lab := _lab()
	assert_str(lab.chassis).is_equal("bushwacker")
	assert_bool(lab._confirm.disabled).is_true()
	# A full stock 'Mech: the AC/5 lights nothing and says why.
	lab.sel = 100
	lab._refresh()
	for loc in Loadout.LOCS:
		assert_float(lab._locs[loc].modulate.a).is_less(1.0)
	lab._install("larm")
	assert_str(lab.msg["k"]).is_equal("bad")
	# Strip the AC/10 (to stores), fit the AC/5 (bought) and a heat sink (from stores).
	lab._remove("larm", 0)
	assert_str(lab.msg["t"]).contains("moved to stores")
	lab._install("larm")
	assert_str(lab.msg["k"]).is_equal("good")
	lab.sel = 7
	lab._install("larm")
	assert_array(lab.work["larm"]).is_equal([100, 7])
	var q := lab._quote()
	assert_int(q["cost"]).is_equal(int(GameData.components[100]["rp"]))
	assert_dict(q["from_stores"]).is_equal({7: 1})
	assert_bool(lab._confirm.disabled).is_false()
	assert_str(lab._vname.text).is_equal("Bushwacker Prime (modified)")
	# An unpaid part taken out again is simply not bought.
	lab._remove("larm", 0)
	assert_str(lab.msg["t"]).contains("never paid for")
	assert_int(lab._quote()["cost"]).is_equal(0)
	# Revert returns to the loadout it came in with.
	lab._revert.pressed.emit()
	assert_bool(Loadout.same(lab.work, lab.entry)).is_true()
