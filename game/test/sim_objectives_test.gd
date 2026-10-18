extends GdUnitTestSuite
## mc2_01 objective chain: airfield -> hangar -> patrol -> north island -> bandits -> extraction.

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_01", 4)


func _obj(i: int) -> Dictionary:
	return sm.objectives.objectives[i]


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
	_step()
	assert_bool(_obj(2)["complete"]).is_true()
	assert_bool(_obj(6)["complete"]).is_true()  # hidden trigger sets flag 3
	assert_bool(o.is_active(_obj(3))).is_true()


func test_extraction_needs_all_previous_primaries() -> void:
	var o := sm.objectives
	o.flags["5"] = true
	assert_bool(o.is_active(_obj(5))).is_false()
	for i in 5:
		_obj(i)["complete"] = true
	assert_bool(o.is_active(_obj(5))).is_true()


func test_win_after_delay() -> void:
	var o := sm.objectives
	for i in 5:
		_obj(i)["complete"] = true
	o.flags["5"] = true
	for m in _player():
		m.position = _obj(5)["conditions"][0]["center"]
	var ev := _step(int(SimObjectives.END_DELAY / SimWorld.TICK) + 3)
	assert_int(o.result).is_equal(SimObjectives.Result.WON)
	assert_bool(ev.any(func(e): return e["type"] == "mission_end" and e["won"])).is_true()


func test_lose_when_all_player_units_down() -> void:
	for m in _player():
		m.status = SimUnit.Status.DISABLED
	_step(int(SimObjectives.END_DELAY / SimWorld.TICK) + 3)
	assert_int(sm.objectives.result).is_equal(SimObjectives.Result.LOST)
