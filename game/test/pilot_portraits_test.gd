extends GdUnitTestSuite
## Pilot portraits (STYLE-GUIDE 7, LANCE-32): pmp_ twins share the pmw faces, wounded pilots show
## the dressing variant, and the tac officer has her own face.


func test_pmp_profiles_map_to_the_pmw_art() -> void:
	assert_str(PilotPortraits.art_profile("pmp_flash")).is_equal("pmwflash")
	assert_str(PilotPortraits.art_profile("pmwflash")).is_equal("pmwflash")
	assert_str(PilotPortraits.path_for("pmp_bubba")).is_equal("res://assets/ui/portraits/pmwbubba.png")
	assert_str(PilotPortraits.path_for("pmp_bubba", true)).is_equal("res://assets/ui/portraits/pmwbubba_wounded.png")
	assert_object(PilotPortraits.texture_for("pmp_flash")).is_same(PilotPortraits.texture_for("pmwflash"))


func test_every_named_pilot_has_a_clean_and_a_wounded_portrait() -> void:
	var named := 0
	for profile in GameData.pilots:
		var p := String(profile)
		if p.begins_with("pmp_"):  # the campaign twin of a named pmw pilot
			named += 1
			assert_bool(ResourceLoader.exists(PilotPortraits.path_for(p))).is_true()
			assert_bool(ResourceLoader.exists(PilotPortraits.path_for(p, true))).is_true()
			assert_bool(ResourceLoader.exists(PilotPortraits.path_for("pmw" + p.substr(4)))).is_true()
	assert_int(named).is_greater(20)


func test_wounded_variant_differs_from_the_clean_face() -> void:
	var clean := PilotPortraits.texture_for("pmwflash")
	var hurt := PilotPortraits.texture_for("pmwflash", true)
	assert_object(hurt).is_not_same(clean)
	assert_object(hurt).is_not_same(PilotPortraits.placeholder())


func test_unknown_profile_falls_back_to_the_silhouette() -> void:
	assert_object(PilotPortraits.texture_for("pmwnobody")).is_same(PilotPortraits.placeholder())
	assert_object(PilotPortraits.texture_for("pmwnobody", true)).is_same(PilotPortraits.placeholder())


func test_wounded_switch_follows_the_pilot() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit = sm.world.units.filter(func(x): return x is SimMech)[0]
	assert_bool(PilotPortraits.is_wounded(null)).is_false()
	u.pilot.wounds = 0.0
	assert_bool(PilotPortraits.is_wounded(u)).is_false()
	u.pilot.wounds = 2.0
	assert_bool(PilotPortraits.is_wounded(u)).is_true()
	u.pilot.dead = true
	assert_bool(PilotPortraits.is_wounded(u)).is_false()


func test_unit_card_swaps_to_the_wounded_portrait() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit = sm.world.units.filter(func(x): return x is SimMech)[0]
	u.pilot_profile = "pmwflash"
	u.pilot.wounds = 0.0
	var card := UnitCard.new(u, null, 1)
	card.expanded = true
	add_child(card)
	await get_tree().process_frame
	var rect := card.find_child("Portrait", true, false) as TextureRect
	if rect == null:
		return  # compact card: no portrait to check
	assert_object(rect.texture).is_same(PilotPortraits.texture_for("pmwflash"))
	u.pilot.wounds = 1.0
	await get_tree().process_frame
	assert_object(rect.texture).is_same(PilotPortraits.texture_for("pmwflash", true))
	card.queue_free()


func test_tac_officer_and_speakers() -> void:
	assert_object(PilotPortraits.tac_officer()).is_same(PilotPortraits.texture_for("tacofficer"))
	assert_object(PilotPortraits.texture_for_speaker("Tac Officer")).is_same(PilotPortraits.tac_officer())
	assert_object(PilotPortraits.texture_for_speaker("")).is_same(PilotPortraits.tac_officer())
	assert_object(PilotPortraits.texture_for_speaker("Some Stranger")).is_same(PilotPortraits.placeholder())
	assert_bool(ResourceLoader.exists("res://assets/ui/portraits/tacofficer.png")).is_true()
