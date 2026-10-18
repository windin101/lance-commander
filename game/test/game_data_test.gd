extends GdUnitTestSuite


func test_atlas_loads() -> void:
	var atlas: Dictionary = GameData.chassis["atlas"]
	assert_str(atlas["name"]).is_equal("Atlas")
	assert_int(int(atlas["tonnage"])).is_equal(100)
	assert_str(atlas["variants"][0]["name"]).is_equal("Atlas Prime")


func test_component_lookup_and_strings() -> void:
	var er_laser: Dictionary = GameData.components[143]
	assert_str(er_laser["weapon"]["range"]).is_equal("medium")
	assert_str(GameData.string(28919)).is_equal("ATLAS")


func test_rule_tables_present() -> void:
	assert_int(GameData.gamesys["Mech:FireWeapon"]["HitLocationTable"].size()).is_equal(132)
	assert_int(GameData.heat_table.size()).is_equal(31)
