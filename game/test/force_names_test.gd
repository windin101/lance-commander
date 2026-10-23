extends GdUnitTestSuite
## Force names (Phase 8): mission colours -> the faction's display name, in the briefing's
## intel, on the HUD's enemy tag and in the debrief's kills.


func test_triples_name_the_force() -> void:
	# mc2_02's bandits: BaseColor #b02828 is the triple's first entry (base|hl1|hl2)
	assert_str(ForceNames.for_paint([0xffddbb50, 0xff000000, 0xffb02828])).is_equal("Bandit Legion")
	assert_str(ForceNames.for_paint([0, 0, 0x123456])).is_empty()  # unmapped
	assert_str(ForceNames.for_paint([])).is_empty()


func test_briefing_lists_the_forces_present() -> void:
	assert_dict(MissionBrief.load_mission(GameData, "mc2_02").forces["opposing"]).contains_keys(["Bandit Legion"])
	var b := MissionBrief.load_mission(GameData, "mc2_17")
	assert_dict(b.forces["opposing"]).contains_keys(["Steiner Guards", "Liao Armored Cavalry"])
	assert_dict(b.forces["allied"]).contains_keys(["Steiner Guards"])


func test_enemy_tag_and_debrief_kills_carry_the_force() -> void:
	var view: Node3D = auto_free(load("res://scenes/mission_view.tscn").instantiate())
	view.mission = "mc2_02"
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var enemy: SimUnit = view.world.units.filter(func(u): return u.team != view.sm.player_team and u.is_mover() \
		and ForceNames.of_unit(u) != "")[0]
	view.hud.show_enemy_tag(enemy, Vector2(400, 300))
	assert_bool(view.hud.enemy_tag.visible).is_true()
	assert_str(view.hud._enemy_force.text).is_equal("Bandit Legion")
	view.hud.show_enemy_tag(null)
	assert_bool(view.hud.enemy_tag.visible).is_false()
	enemy.status = SimUnit.Status.DESTROYED
	var r := MissionReport.from_sim(view.sm, "t", GameData)
	var k: Dictionary = r["kills"].filter(func(e): return e["name"] == enemy.name)[0]
	assert_str(k["force"]).is_equal("Bandit Legion")
	# a player unit gets no force name
	var own: SimUnit = view.world.units.filter(func(u): return u.team == view.sm.player_team and u.commander == 0 and u.is_mover())[0]
	assert_str(ForceNames.of_unit(own)).is_empty()


## The tac map's sensor rings follow the original's scale: range plus six cells, over the map width.
func test_tac_map_sensor_ring_scale() -> void:
	var view: Node3D = auto_free(load("res://scenes/mission_view.tscn").instantiate())
	view.mission = "mc2_02"
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var mm: Minimap = view.hud.minimap
	var expect := (400.0 + mm.map.cell_m * 6.0) / (2.0 * mm.map.half_m) * mm.size.x
	assert_float(mm.sensor_ring_px(400.0)).is_equal_approx(expect, 0.01)
	assert_float(mm.sensor_ring_px(0.0)).is_equal(0.0)
	var rings := mm.rings()
	assert_bool(rings.any(func(r): return r[2] == UiStyle.HUD_OK)).is_true()  # the lance's own sensors
