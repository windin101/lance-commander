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


# --- Mech Lab (issue I86) -------------------------------------------------------------------

func test_new_mechs_carry_their_stock_loadout() -> void:
	var m := camp.add_mech("bushwacker", 0)
	assert_str(m["loadout"]["name"]).is_equal("Bushwacker Prime")
	assert_dict(m["loadout"]["parts"]).is_equal(Loadout.stock_parts(GameData, "bushwacker", 0))
	assert_int(camp.mech_value(m)).is_equal(camp.price("bushwacker", 0))


func test_refit_charges_parts_bought_and_fills_stores() -> void:
	var m := camp.add_mech("bushwacker", 0)
	var p := Loadout.copy(m["loadout"]["parts"])
	p["larm"] = [100]  # AC/10 -> AC/5 (on mc2_02's market)
	assert_str(camp.refit_problem(m, p, "mc2_02")).is_empty()
	assert_bool(camp.refit(m, p, "mc2_02")).is_true()
	assert_int(camp.c_bills).is_equal(80000 - int(GameData.components[100]["rp"]))
	assert_dict(camp.stores).is_equal({101: 1})
	assert_str(m["loadout"]["name"]).is_equal("Bushwacker Prime (modified)")
	# Back to stock: the AC/10 comes out of stores for free and the AC/5 goes in.
	var before := camp.c_bills
	assert_bool(camp.refit(m, Loadout.stock_parts(GameData, "bushwacker", 0), "mc2_02")).is_true()
	assert_int(camp.c_bills).is_equal(before)
	assert_dict(camp.stores).is_equal({100: 1})
	assert_str(m["loadout"]["name"]).is_equal("Bushwacker Prime")
	# Illegal loadouts and parts not for sale are refused.
	var bad := Loadout.copy(p)
	bad["head"] = [114]
	assert_bool(camp.refit(m, bad, "mc2_02")).is_false()
	var off := Loadout.copy(Loadout.stock_parts(GameData, "bushwacker", 0))
	off["rarm"] = [146]  # ER PPC: not on mc2_02's market
	assert_str(camp.refit_problem(m, off, "mc2_02")).contains("not for sale")


func test_saved_variant_applies_to_another_mech() -> void:
	var a := camp.add_mech("bushwacker", 0)
	var b := camp.add_mech("bushwacker", 0)
	var w := camp.add_mech("werewolf", 0)
	var p := Loadout.copy(a["loadout"]["parts"])
	p["larm"] = [100, 7]  # AC/5 and a heat sink
	assert_bool(camp.save_variant("bushwacker", "Bushwacker Prime", p)).is_false()  # designer name
	assert_bool(camp.save_variant("bushwacker", "Cool Runner", p)).is_true()
	assert_bool(camp.refit(a, p, "mc2_02")).is_true()
	assert_str(a["loadout"]["name"]).is_equal("Cool Runner")
	var sv: Dictionary = camp.variants_for("bushwacker")[0]
	assert_bool(camp.apply_variant(w, sv, "mc2_02")).is_false()  # another chassis
	assert_bool(camp.apply_variant(b, sv, "mc2_02")).is_true()
	assert_dict(b["loadout"]["parts"]).is_equal(p)
	assert_str(b["loadout"]["name"]).is_equal("Cool Runner")


func test_save_and_load_keep_loadouts_stores_and_variants() -> void:
	var m := camp.add_mech("bushwacker", 0, "pmwhacksaw", 1)
	var p := Loadout.copy(m["loadout"]["parts"])
	p["larm"] = [100]
	camp.save_variant("bushwacker", "Light Gun", p)
	camp.refit(m, p, "mc2_02")
	var d: Dictionary = JSON.parse_string(JSON.stringify(camp.to_dict()))
	var c2 := Campaign.create(GameData)
	c2.from_dict(d)
	assert_dict(c2.mechs[0]["loadout"]["parts"]).is_equal(p)
	assert_str(c2.mechs[0]["loadout"]["name"]).is_equal("Light Gun")
	assert_dict(c2.stores).is_equal({101: 1})
	assert_int(c2.saved_variants.size()).is_equal(1)
	assert_dict(c2.saved_variants[0]["parts"]).is_equal(p)
	# The force carries the refit to the sim.
	var f: Dictionary = c2.force()[0]
	assert_bool(f["loadout"]["items"].has(100)).is_true()
	assert_bool(f["loadout"]["items"].has(101)).is_false()


## A save from before the Mech Lab holds a variant index only: it loads as that stock design.
func test_old_saves_migrate_to_stock_loadouts() -> void:
	var old := {"c_bills": 5000, "next_id": 3, "mechs": [{"id": 1, "chassis": "werewolf", "variant": 0, "pilot": "", "slot": 0},
		{"id": 2, "chassis": "bushwacker", "variant": 0.0, "pilot": "pmwflash", "slot": 1.0}]}
	camp.from_dict(JSON.parse_string(JSON.stringify(old)))
	assert_int(camp.mechs.size()).is_equal(2)
	assert_dict(camp.mechs[1]["loadout"]["parts"]).is_equal(Loadout.stock_parts(GameData, "bushwacker", 0))
	assert_str(camp.mechs[0]["loadout"]["name"]).is_equal("Razorback Prime")
	assert_dict(camp.stores).is_empty()
	assert_array(camp.saved_variants).is_empty()


func test_win_keeps_a_survivors_refit() -> void:
	var m := camp.add_mech("bushwacker", 0, "pmwflash", 1)
	var p := Loadout.copy(m["loadout"]["parts"])
	p["larm"] = [100]
	camp.refit(m, p, "mc2_02")
	camp.apply_win({"payout": 0, "survivors": [{"chassis": "bushwacker", "variant": 0, "pilot": "pmwflash",
		"loadout": {"name": "Bushwacker Prime (modified)", "parts": p}}], "pilots": []})
	assert_int(camp.mechs.size()).is_equal(1)
	assert_dict(camp.mechs[0]["loadout"]["parts"]).is_equal(p)
	# Selling a refitted 'Mech pays its value with the new parts.
	camp.withdraw(camp.mechs[0])
	var before := camp.c_bills
	var value := camp.mech_value(camp.mechs[0])
	assert_int(value).is_equal(camp.price("bushwacker", 0) - int(GameData.components[101]["rp"]) + int(GameData.components[100]["rp"]))
	assert_bool(camp.sell(camp.mechs[0])).is_true()
	assert_int(camp.c_bills).is_equal(before + value)
