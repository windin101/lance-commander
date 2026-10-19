extends GdUnitTestSuite
## Campaign layer (docs/specs/campaign-layer.md): prices, purchase lists, the drop
## limits, the campaign force replacing a mission's lance, and applying a win.

var camp: Campaign


func before_test() -> void:
	camp = Campaign.create(GameData)


func test_new_campaign() -> void:
	assert_int(camp.c_bills).is_equal(80000)
	assert_int(camp.pilots.size()).is_greater(40)
	assert_str(camp.pilots["pmwflash"]["name"]).is_equal("Flash")
	assert_bool(camp.plays_logistics("mc2_01")).is_false()
	assert_bool(camp.plays_logistics("mc2_02")).is_true()


func test_variant_price_is_chassis_plus_components() -> void:
	var ch: Dictionary = GameData.chassis["hunchback"]
	var expected := int(ch["cbills"])
	for id in ch["variants"][0]["items"]:
		if id != null:
			expected += int(GameData.components[int(id)]["rp"])
	assert_int(camp.price("hunchback", 0)).is_equal(expected)
	assert_int(camp.salvage_price("hunchback", 0)).is_equal(int(0.8 * expected))


func test_purchase_list_follows_the_mission_file() -> void:
	var names := camp.purchasable("mc2_02").map(func(o): return o["chassis"])
	assert_bool(names.has("hunchback")).is_true()
	assert_bool(names.has("atlas")).is_false()
	assert_bool(camp.available_pilots("mc2_02").has("pmwflash")).is_true()


func test_drop_weight_and_slots() -> void:
	var a := camp.add_mech("atlas", 0)
	var b := camp.add_mech("atlas", 0)
	var limit := camp.drop_limit("mc2_02")
	assert_bool(camp.deploy(a, "mc2_02")).is_equal(camp.tonnage("atlas") <= limit)
	if int(a["slot"]) > 0:
		assert_bool(camp.deploy(b, "mc2_02")).is_equal(2.0 * camp.tonnage("atlas") <= limit)
	assert_str(camp.launch_problem("mc2_02")).is_not_empty()  # no pilot yet


func test_buy_sell_and_win() -> void:
	var cost := camp.price("hunchback", 0)
	assert_bool(camp.buy("hunchback", 0)).is_true()
	assert_int(camp.c_bills).is_equal(80000 - cost)
	var m: Dictionary = camp.mechs[0]
	camp.deploy(m, "mc2_02")
	m["pilot"] = "pmwflash"
	camp.apply_win({"payout": 5000, "survivors": [{"chassis": "hunchback", "variant": 0, "pilot": "pmwflash"}],
		"pilots": [{"profile": "pmwflash", "kills": ["heavy", "vehicle"], "dead": false}]})
	assert_int(camp.c_bills).is_equal(80000 - cost + 5000)
	assert_int(camp.deployed().size()).is_equal(1)
	assert_float(camp.pilots["pmwflash"]["gunnery"]).is_greater(float(GameData.pilots["pmwflash"]["Skills"]["Gunnery"]))
	assert_int(camp.pilots["pmwflash"]["kills"]).is_equal(2)


func test_force_replaces_the_missions_lance() -> void:
	var force := [{"chassis": "atlas", "variant": 0, "pilot": "pmwflash", "gunnery": 60.0, "piloting": 55.0},
		{"chassis": "hunchback", "variant": 0, "pilot": "pmwhacksaw", "gunnery": 50.0, "piloting": 50.0}]
	var sm := SimMission.load_mission(GameData, "mc2_02", 1, true, force)
	var lance := sm.world.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover())
	assert_int(lance.size()).is_equal(2)
	assert_str(lance[0].model).is_equal("atlas")
	assert_int(lance[0].part_id).is_equal(512)
	assert_float(lance[0].pilot.gunnery).is_equal(60.0)
	assert_bool(lance[0].brain is SimAbl.Pilot).is_true()
	assert_float(lance[0].position.distance_to(lance[1].position)).is_less(60.0)
	var r := MissionReport.from_sim(sm, "t", GameData)
	assert_int(r["survivors"].size()).is_equal(2)
	assert_str(r["pilots"][0]["profile"]).is_equal("pmwflash")
