extends GdUnitTestSuite
## HUD pieces: damage-diagram colours, minimap mapping, card selection, alpha strike, and the
## approved-mock-up HUD: lance rows, expanded card, systems monitor, scale, doll masks.

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
	view.play_intro = false
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


func test_hud_unit_follows_viewport_height_and_setting() -> void:
	assert_float(UiStyle.hud_unit(1080.0, 0.7)).is_equal_approx(0.0085 * 1920.0 * 0.7, 0.001)
	assert_float(UiStyle.hud_unit(2160.0, 0.7)).is_equal_approx(2.0 * UiStyle.hud_unit(1080.0, 0.7), 0.001)
	assert_float(UiStyle.hud_unit(720.0, 1.0)).is_equal_approx(0.0085 * 1920.0 * 720.0 / 1080.0, 0.001)
	var keep := UiStyle.hud_scale()
	UiStyle.set_hud_scale(5.0, false)
	assert_float(UiStyle.hud_scale()).is_equal(UiStyle.HUD_SCALE_MAX)
	UiStyle.set_hud_scale(0.1, false)
	assert_float(UiStyle.hud_scale()).is_equal(UiStyle.HUD_SCALE_MIN)
	UiStyle.set_hud_scale(keep, false)


func test_doll_mask_and_fallback() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var mech: SimUnit = sm.world.units[0]
	assert_bool(PaperDoll.mask_for("no_such_unit").is_empty()).is_true()
	var d := DollView.new(mech)
	mech.model = "no_such_unit"
	d.set_unit(mech)
	assert_bool(d.has_mask()).is_false()  # rectangle layout fallback
	assert_object(d.material).is_null()
	mech.model = "werewolf"
	d.set_unit(mech)
	if FileAccess.file_exists(PaperDoll.DOLL_DIR + "/werewolf_doll.png"):
		assert_bool(d.has_mask()).is_true()
		assert_object(d.material).is_not_null()
		var r: Rect2 = d.mask["region"]
		assert_float(r.size.x).is_greater(8.0)
	d.free()
	# rear: only the torso is lit, from the rear armour
	mech.armor[SimMech.Armor.RCTORSO] = 0.0
	var rear := PaperDoll.location_colours(mech, true)
	var front := PaperDoll.location_colours(mech, false)
	assert_object(rear[SimMech.Body.CTORSO]).is_equal(PaperDoll.HOLED)
	assert_object(front[SimMech.Body.CTORSO]).is_equal(PaperDoll.OK)
	assert_float(rear[SimMech.Body.LARM].a).is_less(0.5)


func test_weapon_groups() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var g: Array = SystemsMonitor.weapon_groups(sm.world.units[0])  # Werewolf
	assert_array(g.map(func(x): return x["label"])).contains_exactly(["Streak SRM2 ×2", "Large Laser", "MG Array ×3"])
	assert_str(g[1]["range"]).is_equal("medium")


func test_lance_rows_expand_and_systems_monitor() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	await get_tree().process_frame
	var hud: MissionHud = view.hud
	var units := hud.player_units()
	assert_int(units.size()).is_equal(3)
	assert_int(hud.lance_list.get_child_count()).is_equal(units.size())  # one row per unit
	for u in units:
		assert_bool(hud.cards[u.id].expanded).is_false()
	assert_bool(hud.systems.visible).is_false()
	assert_bool(hud.comms.visible).is_false()
	assert_float(hud.unit_px).is_equal_approx(UiStyle.hud_unit(hud.get_viewport().get_visible_rect().size.y), 0.01)
	assert_float(hud.coverage()).is_less(0.2)  # at rest
	var u: SimUnit = units[1]
	view.input._set_selection([u])
	await get_tree().process_frame
	assert_bool(hud.cards[u.id].expanded).is_true()
	assert_bool(hud.cards[units[0].id].expanded).is_false()
	assert_bool(hud.cards[u.id].buttons.has("stop")).is_true()
	assert_bool(hud.systems.visible).is_true()
	assert_object(hud.systems.unit).is_same(u)
	# card STOP and the panel's alpha strike reach the orders
	hud._on_command("alpha_strike")
	assert_bool(u.ignore_heat_discipline).is_true()
	hud._on_command("guard")
	assert_str(hud.command_mode).is_equal("guard")
	hud._on_card_order(u, "stop")
	assert_str(hud.command_mode).is_equal("")
	# a pilot talking: comms up, the card blinks
	hud.pilot_says(u, "Contact.", 5.0)
	await get_tree().process_frame
	assert_bool(hud.comms.visible).is_true()
	assert_bool(hud.cards[u.id].speaking).is_true()
	view.input._set_selection([])
	await get_tree().process_frame
	assert_bool(hud.systems.visible).is_false()
	assert_bool(hud.cards[u.id].expanded).is_false()
	# the HUD rebuilds at a new scale
	var keep := UiStyle.hud_scale()
	var before := hud.unit_px
	UiStyle.set_hud_scale(1.0 if keep < 0.95 else 0.6, false)
	await get_tree().process_frame
	assert_bool(absf(hud.unit_px - before) > 0.01).is_true()
	assert_int(hud.cards.size()).is_equal(3)
	UiStyle.set_hud_scale(keep, false)
	view.queue_free()


## The tac-map camera footprint moves the way the camera moves and is ordered as a convex quad (Lee 2026-10-21:
## "if I move the screen right the tac map goes left").
func test_footprint_follows_camera() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	for i in 6:
		await get_tree().process_frame
	var hud: MissionHud = view.hud
	var cam: RtsCamera = view.camera
	cam.yaw_deg = 0.0
	var start := Vector2(cam.focus.x, -cam.focus.z)
	cam.pan_to(start)
	for i in 4:
		await get_tree().process_frame
	var c0 := _centroid(hud._camera_footprint())
	print("footprint at yaw 0: ", hud._camera_footprint(), " focus ", start)
	cam.pan_to(start + Vector2(200, 0))  # east
	for i in 4:
		await get_tree().process_frame
	var c1 := _centroid(hud._camera_footprint())
	cam.pan_to(start + Vector2(0, 200))  # north
	for i in 4:
		await get_tree().process_frame
	var c2 := _centroid(hud._camera_footprint())
	print("centroids ", c0, " east ", c1, " north ", c2)
	assert_float(c1.x - c0.x).is_greater(100.0)
	assert_float(c2.y - c0.y).is_greater(100.0)
	view.queue_free()


func _centroid(p: PackedVector2Array) -> Vector2:
	var s := Vector2.ZERO
	for v in p:
		s += v
	return s / maxf(1.0, p.size())
