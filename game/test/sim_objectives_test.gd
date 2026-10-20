extends GdUnitTestSuite
## mc2_01 objective chain: airfield -> hangar -> patrol -> north island -> bandits -> extraction.

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_01", 4)


func _obj(i: int) -> Dictionary:
	return sm.objectives.objectives[i]


func _succeed(i: int) -> void:
	_obj(i)["active"] = true
	_obj(i)["status"] = SimObjectives.Status.SUCCESS
	_obj(i)["complete"] = true


func _player() -> Array:
	return sm.world.units.filter(func(u): return u.team == 0 and u.is_mover())


func _step(n: int = 1) -> Array:
	var ev := []
	for i in n:
		sm.step()
		ev.append_array(sm.world.events)
		sm.world.events.clear()
	return ev


func test_objectives_load_and_resolve_targets() -> void:
	var o := sm.objectives
	assert_int(o.objectives.size()).is_equal(9)
	assert_array(o.unsupported).is_empty()
	assert_str(_obj(1)["title"]).is_equal("2. Destroy Hangar")
	assert_object(_obj(1)["conditions"][0]["unit"]).is_not_null()
	for c in _obj(2)["conditions"]:
		assert_object(c["unit"]).override_failure_message("patrol unit not resolved").is_not_null()
	assert_bool(_obj(6)["hidden"]).is_true()
	assert_bool(o.is_active(_obj(0))).is_true()
	assert_bool(o.is_active(_obj(1))).is_false()  # waits on flag 0


func test_chain_airfield_hangar_patrol() -> void:
	var o := sm.objectives
	var mech: SimUnit = _player()[0]
	mech.position = _obj(0)["conditions"][0]["center"]
	_step()
	assert_bool(_obj(0)["complete"]).is_true()
	assert_bool(o.flags.get("0", false)).is_true()
	assert_bool(o.is_active(_obj(1))).is_true()
	var hangar: SimStructure = _obj(1)["conditions"][0]["unit"]
	hangar.take_hit(sm.world.rules, sm.world.rng, 25.0, 0, 143, 0.0)
	_step()
	assert_bool(_obj(1)["complete"]).is_true()
	assert_bool(o.is_active(_obj(2))).is_true()
	for c in _obj(2)["conditions"]:
		c["unit"].status = SimUnit.Status.DESTROYED
	_step(2)  # a flag-activated objective is evaluated from the sweep after it activates
	assert_bool(_obj(2)["complete"]).is_true()
	assert_bool(_obj(6)["complete"]).is_true()  # hidden trigger sets flag 3
	assert_bool(o.is_active(_obj(3))).is_true()


func test_extraction_needs_all_previous_primaries() -> void:
	var o := sm.objectives
	o.flags["5"] = true
	_step()  # the flag activates it; the earlier primaries still gate it
	assert_bool(_obj(5)["active"]).is_true()
	assert_bool(o.is_active(_obj(5))).is_false()
	for i in 5:
		_succeed(i)
	assert_bool(o.is_active(_obj(5))).is_true()


func test_win_after_delay() -> void:
	var o := sm.objectives
	for i in 5:
		_succeed(i)
	o.flags["5"] = true
	var area: Vector2 = _obj(5)["conditions"][0]["center"]
	for m in _player():
		m.position = area
	# Extraction also needs no other commander's unit within 256 m (the Starslayer's group).
	for u in sm.world.units:
		if u.is_mover() and u.team != 0 and u.position.distance_to(area) <= SimObjectives.EXTRACT_CLEAR_M:
			u.status = SimUnit.Status.DESTROYED
	var ev := _step(int(SimObjectives.END_DELAY / SimWorld.TICK) + 3)
	assert_int(o.result).is_equal(SimObjectives.Result.WON)
	assert_bool(ev.any(func(e): return e["type"] == "mission_end" and e["won"])).is_true()


func test_lose_when_all_player_units_down() -> void:
	for m in _player():
		m.status = SimUnit.Status.DISABLED
	_step(int(SimObjectives.END_DELAY / SimWorld.TICK) + 3)
	assert_int(sm.objectives.result).is_equal(SimObjectives.Result.LOST)



func test_extraction_blocked_while_enemies_near() -> void:
	var o := sm.objectives
	for i in 5:
		_succeed(i)
	o.flags["5"] = true
	var area: Vector2 = _obj(5)["conditions"][0]["center"]
	for m in _player():
		m.position = area
	var blocker: SimUnit = sm.world.units.filter(func(u): return u.is_mover() and u.team != 0)[0]
	blocker.position = area + Vector2(100, 0)
	_step(3)
	assert_bool(_obj(5)["complete"]).is_false()


## I11 (mission.cpp:1106-1124): a part placed destroyed (FIT Damage >= 1.0) spawns shut down and off the GUI
## when it is the home commander's (mc2_08's Atlas, Part2), disabled otherwise (mc2_11's salvage-yard mechs).
func test_parts_placed_destroyed() -> void:
	var s8 := SimMission.load_mission(GameData, "mc2_08", 4)
	var atlas: SimUnit = null
	for u in s8.world.units:
		if u.part_index == 2:
			atlas = u
	assert_object(atlas).is_not_null()
	assert_int(atlas.status).is_equal(SimUnit.Status.SHUTDOWN)
	assert_bool(atlas.on_gui).is_false()
	assert_bool(s8.objectives._player_force(atlas)).is_false()
	var s11 := SimMission.load_mission(GameData, "mc2_11", 4)
	for u in s11.world.units:
		if u.part_index in [9, 10, 11, 14, 39]:
			assert_bool(u.is_disabled()).is_true()
