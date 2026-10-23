extends GdUnitTestSuite
## Paint schemes: the player's setting (default, save, load), who wears which scheme, the sculpt-prop loader order.

const TEST_CFG := "user://test_paint_scheme.cfg"


func before_test() -> void:
	PaintScheme.settings_path = TEST_CFG
	PaintScheme.reset_cache()
	if FileAccess.file_exists(TEST_CFG):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_CFG))


func after_test() -> void:
	if FileAccess.file_exists(TEST_CFG):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_CFG))
	PaintScheme.settings_path = "user://settings.cfg"
	PaintScheme.reset_cache()


func test_default_is_grey_with_red_piping() -> void:
	var s := PaintScheme.player()
	assert_str(String(s["base"])).is_equal("#9a9a9a")
	assert_str(String(s["hl1"])).is_equal("#d02e11")
	assert_str(String(s["pattern"])).is_equal("plain")
	assert_str(String(s["piping"])).is_equal("hl1")


func test_player_scheme_saves_and_loads() -> void:
	PaintScheme.set_player(Color("#2b3038"), Color("#3aa0d8"), Color("#16181c"), "urban")
	PaintScheme.reset_cache()
	PaintScheme.settings_path = TEST_CFG
	var s := PaintScheme.player()
	assert_str(String(s["base"])).is_equal("#2b3038")
	assert_str(String(s["hl1"])).is_equal("#3aa0d8")
	assert_str(String(s["pattern"])).is_equal("urban")


func test_unknown_pattern_falls_back_to_plain() -> void:
	PaintScheme.set_player(Color.GRAY, Color.RED, Color.BLACK, "polka", false)
	assert_str(String(PaintScheme.player()["pattern"])).is_equal("plain")


func test_player_units_wear_the_player_scheme_enemies_their_own() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_17")
	var mine := 0
	var steiner := 0
	for u in sm.world.units:
		var s := PaintScheme.for_unit(u)
		if u.is_player and u.commander == 0:
			mine += 1
			assert_str(String(s.get("owner", ""))).is_equal("player")
		elif String(s.get("faction", "")) == "steiner":
			steiner += 1
	assert_int(mine).is_greater(0)
	assert_int(steiner).is_greater(0)


func test_faction_and_mission_colours_by_triple() -> void:
	# [HighlightColor1, HighlightColor2, BaseColor] as SimUnit.paint
	var liao := PaintScheme.for_triple([0xfff4c28a, 0xffde701f, 0xff809267])
	assert_str(String(liao.get("faction", ""))).is_equal("liao")
	assert_str(String(liao["base"])).is_equal("#003914")
	var bandit := PaintScheme.for_triple([0xffddbb50, 0xff000000, 0xffb02828])
	assert_str(String(bandit.get("faction", ""))).is_equal("bandits")
	assert_str(String(bandit["pattern"])).is_equal("arkab")
	var rebel := PaintScheme.for_triple([0xffffff80, 0xffffff80, 0xffff8080])   # mc2_17 rebels: their own colours
	assert_str(String(rebel.get("mode", ""))).is_equal("mask")
	assert_str(String(rebel["base"])).is_equal("#ff8080")


func test_sculpt_props_beat_upscaled_originals() -> void:
	if not ResourceLoader.exists("res://assets/objects/privatejet_hd.glb"):
		return
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var ov := ObjectsView.new()
	add_child(ov)
	ov.build(sm.world.map, "mc2_01")
	var found := 0
	for i in ov.nodes:
		var app: String = ov._appearance[i]
		if app in ["privatejet", "shilonep", "slayerp"]:
			assert_str((ov.nodes[i] as Node3D).scene_file_path).is_equal("res://assets/objects/%s_hd.glb" % app)
			found += 1
	assert_int(found).is_greater(0)
	ov.queue_free()
