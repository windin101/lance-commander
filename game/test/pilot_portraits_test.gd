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


func test_memorial_path_follows_the_art_profile() -> void:
	assert_str(PilotPortraits.memorial_path_for("pmp_flash")).is_equal("res://assets/ui/portraits/pmwflash_memorial.png")
	assert_str(PilotPortraits.memorial_path_for("pmwsteel")).is_equal("res://assets/ui/portraits/pmwsteel_memorial.png")


func test_every_drawn_face_has_a_memorial() -> void:
	var faces := 0
	for f in DirAccess.get_files_at(PilotPortraits.DIR):
		if f.ends_with(".png") and f.begins_with("pmw") and not f.ends_with("_wounded.png") and not f.ends_with("_memorial.png"):
			faces += 1
			assert_bool(PilotPortraits.has_memorial(f.get_basename())).override_failure_message("no memorial for " + f).is_true()
	assert_int(faces).is_equal(33)  # 26 named pilots + the 7 generics a player can see


func test_memorial_is_a_different_picture_from_the_clean_face() -> void:
	var clean := PilotPortraits.texture_for("pmwsteel")
	var memorial := PilotPortraits.memorial_for("pmwsteel")
	assert_object(memorial).is_not_same(clean)
	assert_object(memorial).is_not_same(PilotPortraits.placeholder())
	assert_object(PilotPortraits.memorial_for("pmp_steel")).is_same(memorial)


func test_memorial_is_greyscale_with_a_black_border() -> void:
	for profile in ["pmwsteel", "pmwflash", "pmwhacksaw", "pmwscout", "pmwchopper"]:
		var img := PilotPortraits.memorial_for(profile).get_image()
		assert_int(img.get_width()).is_equal(660)
		assert_int(img.get_height()).is_equal(920)
		for p in [Vector2i(0, 0), Vector2i(5, 400), Vector2i(654, 400), Vector2i(330, 914), Vector2i(330, 4)]:
			assert_float(img.get_pixelv(p).get_luminance()).is_less(0.02)  # the black border
		for p in [Vector2i(330, 200), Vector2i(200, 500), Vector2i(450, 700)]:
			var c := img.get_pixelv(p)
			assert_float(absf(c.r - c.g) + absf(c.g - c.b)).is_less(0.03)  # no colour left in the picture


func test_missing_memorial_falls_back_to_the_clean_face_then_the_silhouette() -> void:
	assert_bool(PilotPortraits.has_memorial("pmwnobody")).is_false()
	assert_object(PilotPortraits.memorial_for("pmwnobody")).is_same(PilotPortraits.placeholder())
	assert_object(PilotPortraits.memorial_for("")).is_same(PilotPortraits.placeholder())


func test_texture_for_unit_picks_memorial_wounded_or_clean() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit = sm.world.units.filter(func(x): return x is SimMech)[0]
	u.pilot_profile = "pmwflash"
	u.pilot.wounds = 0.0
	u.pilot.dead = false
	assert_object(PilotPortraits.texture_for_unit(u)).is_same(PilotPortraits.texture_for("pmwflash"))
	u.pilot.wounds = 2.0
	assert_object(PilotPortraits.texture_for_unit(u)).is_same(PilotPortraits.texture_for("pmwflash", true))
	u.pilot.dead = true  # dead beats wounded
	assert_bool(PilotPortraits.is_dead(u)).is_true()
	assert_object(PilotPortraits.texture_for_unit(u)).is_same(PilotPortraits.memorial_for("pmwflash"))
	assert_object(PilotPortraits.texture_for_unit(u, "pmwsteel")).is_same(PilotPortraits.memorial_for("pmwsteel"))
	assert_bool(PilotPortraits.is_dead(null)).is_false()


func test_unit_card_shows_the_memorial_for_a_dead_pilot() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit = sm.world.units.filter(func(x): return x is SimMech)[0]
	u.pilot_profile = "pmwflash"
	u.pilot.wounds = 0.0
	u.pilot.dead = false
	var card := UnitCard.new(u, null, 1)
	card.expanded = true
	add_child(card)
	await get_tree().process_frame
	var rect := card.find_child("Portrait", true, false) as TextureRect
	if rect == null:
		return
	u.pilot.dead = true
	await get_tree().process_frame
	assert_object(rect.texture).is_same(PilotPortraits.memorial_for("pmwflash"))
	card.queue_free()


func test_comms_window_shows_the_memorial_for_a_dead_pilot() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u: SimUnit = sm.world.units.filter(func(x): return x is SimMech)[0]
	u.pilot_profile = "pmwhacksaw"
	u.pilot.dead = true
	var c := CommsWindow.new()
	add_child(c)
	c.say("HACKSAW", "Still here.", u, 1.0)
	assert_object(c.portrait.texture).is_same(PilotPortraits.memorial_for("pmwhacksaw"))
	c.queue_free()


func test_every_visible_generic_pilot_has_a_clean_a_wounded_and_a_memorial_face() -> void:
	for profile in ["pmwgreen", "pmwregular", "pmwveteran", "pmwscout", "pmwrepair", "pmwminelayer", "pmwguardtower"]:
		for path in [PilotPortraits.path_for(profile), PilotPortraits.path_for(profile, true), PilotPortraits.memorial_path_for(profile)]:
			assert_bool(ResourceLoader.exists(path)).override_failure_message("missing " + path).is_true()
		assert_object(PilotPortraits.texture_for(profile)).is_not_same(PilotPortraits.placeholder())
