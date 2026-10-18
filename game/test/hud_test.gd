extends GdUnitTestSuite
## HUD pieces: damage-diagram colours, minimap mapping, card selection, alpha strike.

func test_paper_doll_colours() -> void:
	assert_object(PaperDoll.color(10, 10, 5, 5)).is_equal(PaperDoll.OK)
	assert_object(PaperDoll.color(5, 10, 5, 5)).is_equal(PaperDoll.SCRATCHED)
	assert_object(PaperDoll.color(1, 10, 5, 5)).is_equal(PaperDoll.HOLED)
	assert_object(PaperDoll.color(0, 10, 3, 5)).is_equal(PaperDoll.CRITICAL)
	assert_object(PaperDoll.color(0, 10, 0, 5)).is_equal(PaperDoll.GONE)


func test_paper_doll_cells_for_mech_and_vehicle() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var mech: SimUnit = sm.world.units[0]
	var veh: SimUnit = sm.world.units.filter(func(u): return u is SimVehicle)[0]
	assert_int(PaperDoll.cells(mech, Rect2(0, 0, 100, 100)).size()).is_equal(8)
	assert_int(PaperDoll.cells(veh, Rect2(0, 0, 100, 100)).size()).is_equal(5)
	mech.internal[SimMech.Body.LARM] = 0.0
	var larm: Array = PaperDoll.cells(mech, Rect2(0, 0, 100, 100))[SimMech.Body.LARM]
	assert_object(larm[1]).is_equal(PaperDoll.GONE)


func test_alpha_strike_bypasses_fire_discipline() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var w := sm.world
	var m: SimUnit = w.units[1]
	var enemy: SimUnit = w.units.filter(func(u): return u is SimMech and u.team != 0)[0]
	enemy.position = m.position + Vector2(0, 60)
	m.facing = 0.0
	m.heat = m.heat_capacity * 21.0 / 30.0  # above the discipline level
	w.order_attack(m, enemy)
	var shots := 0
	for i in 5:
		w.step()
		shots += w.events.filter(func(e): return e["type"] == "shot" and e["from"] == m.id).size()
		w.events.clear()
		m.heat = m.heat_capacity * 21.0 / 30.0
	assert_int(shots).is_equal(0)
	m.ignore_heat_discipline = true
	for i in 5:
		w.step()
		shots += w.events.filter(func(e): return e["type"] == "shot" and e["from"] == m.id).size()
		w.events.clear()
	assert_int(shots).is_greater(0)


func test_hud_in_live_view() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	add_child(view)
	await get_tree().process_frame
	await get_tree().process_frame
	var hud: MissionHud = view.hud
	assert_int(hud.cards.size()).is_equal(3)
	var mm := hud.minimap
	for p in [Vector2(-1000, 900), Vector2(0, 0), Vector2(640, -320)]:
		assert_float(mm.map_to_world(mm.world_to_map(p)).distance_to(p)).is_less(0.01)
	var u: SimUnit = view.world.units[1]
	hud._on_card_picked(u, false)
	assert_bool(view.input.selection.has(u)).is_true()
	view.input.toggle_alpha_strike()
	assert_bool(u.ignore_heat_discipline).is_true()
	view.input.toggle_alpha_strike()
	assert_bool(u.ignore_heat_discipline).is_false()
	assert_int(hud._camera_footprint().size()).is_equal(4)
	view.queue_free()
