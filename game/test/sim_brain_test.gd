extends GdUnitTestSuite
## mc2_01 AI on the mission's original ABL (SimAbl): guards intercept, the airfield
## objective starts patrols, the Starslayer wakes on its trigger, hangar damage
## springs the infantry ambush. The player lance keeps the player-command brain.

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_01", 11)


func _by_brain(name: String) -> Array:
	return sm.world.units.filter(func(u): return u.brain_name == name)


func _run(seconds: float) -> void:
	for i in int(seconds / SimWorld.TICK):
		sm.step()
		sm.world.events.clear()


func test_brains_attached() -> void:
	assert_object(sm.abl).is_not_null()
	assert_int(sm.abl.pilots.size()).is_equal(26)
	assert_array(sm.abl.runtime.errors).is_empty()
	for u in _by_brain("PBrain"):
		assert_bool(u.brain is SimAbl.Pilot).is_false()
	assert_float(_by_brain("PBrain")[0].engage_m).is_equal(100.0)
	# Part IDs from the commander group slots (abl-natives.md 1.3)
	assert_int(sm.world.units.filter(func(u): return u.part_index == 4)[0].part_id).is_equal(704)
	# The building the infantry brains watch: getObjectDamage(116641)
	assert_object(sm.abl.obj(116641)).is_same(sm.structure_near(Vector2(3221.333, -277.333)))


func test_starslayer_starts_powered_down() -> void:
	var ss: SimUnit = _by_brain("mc2_01_Starslayer")[0]
	_run(3.0)
	assert_int(ss.status).is_equal(SimUnit.Status.SHUTDOWN)


func test_guard_intercepts_intruder() -> void:
	var guard: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	var player: SimUnit = _by_brain("PBrain")[0]
	player.position = sm.world.map.nearest_walkable(guard.position + Vector2(0, -250))
	_run(5.0)
	assert_str(guard.brain.inst.state).is_equal("attack")
	assert_object(guard.current_target).is_same(player)


func test_airfield_objective_starts_patrols() -> void:
	var pat: SimUnit = _by_brain("mc2_01_Pat4")[0]
	var start := pat.position
	var mech: SimUnit = _by_brain("PBrain")[0]
	mech.position = sm.objectives.objectives[0]["conditions"][0]["center"]
	_run(1.0)
	assert_bool(sm.world.flags.get("patrol3_triggered", false)).is_true()
	var furthest := 0.0
	for i in 300:
		sm.step()
		sm.world.events.clear()
		furthest = maxf(furthest, pat.position.distance_to(start))
	assert_float(furthest).is_greater(150.0)


func test_starslayer_powers_up_on_trigger() -> void:
	var ss: SimUnit = _by_brain("mc2_01_Starslayer")[0]
	_run(3.0)
	sm.abl.mission_inst.unit["_eternals"]["starslayer_trigger"] = true
	var up_at := -1.0
	for i in 300:
		sm.step()
		sm.world.events.clear()
		if ss.status == SimUnit.Status.NORMAL:
			up_at = sm.world.time
			break
	assert_float(up_at).is_greater(0.0)


func test_hangar_damage_springs_infantry_ambush() -> void:
	var hangar := sm.structure_near(Vector2(3221.333, -277.333))
	hangar.take_hit(sm.world.rules, sm.world.rng, 1.0, 0, 143, 0.0)
	_run(5.0)
	assert_bool(sm.world.flags.get("hangarattacked", false)).is_true()
	var inf: SimUnit = _by_brain("mc2_01_infantry_ambush")[0]
	assert_str(inf.brain.inst.state).is_equal("ambush")


func test_player_returns_fire_when_idle() -> void:
	var player: SimUnit = _by_brain("PBrain")[0]
	var enemy: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	player.last_attacker = enemy
	player.last_attacked_time = 0.05
	_run(0.2)
	assert_int(player.order).is_equal(SimWorld.Order.ATTACK)
	assert_object(player.order_target).is_same(enemy)
