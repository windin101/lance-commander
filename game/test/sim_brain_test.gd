extends GdUnitTestSuite
## mc2_01 AI brains: guards intercept, triggers start patrols, Starslayer wakes,
## infantry ambush on hangar damage, player units return fire.

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
	assert_int(_by_brain("PBrain").size()).is_equal(3)
	assert_int(_by_brain("mc2_01_infantry_ambush").size()).is_equal(5)
	var ss: SimUnit = _by_brain("mc2_01_Starslayer")[0]
	assert_str(ss.brain.state).is_equal("powered_down")
	assert_int(ss.status).is_equal(SimUnit.Status.SHUTDOWN)
	assert_float(_by_brain("PBrain")[0].engage_m).is_equal(100.0)


func test_guard_intercepts_intruder() -> void:
	var guard: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	var player: SimUnit = _by_brain("PBrain")[0]
	player.position = sm.world.map.nearest_walkable(guard.position + Vector2(0, -250))
	_run(2.0)
	assert_str(guard.brain.state).is_equal("attack")
	assert_object(guard.brain.target).is_same(player)


func test_airfield_objective_starts_patrols() -> void:
	var pat: SimUnit = _by_brain("mc2_01_Pat4")[0]
	var start := pat.position
	var mech: SimUnit = _by_brain("PBrain")[0]
	mech.position = sm.objectives.objectives[0]["conditions"][0]["center"]
	_run(1.0)
	assert_bool(sm.world.flags.get("patrol3", false)).is_true()
	assert_str(pat.brain.state).is_equal("patrol")
	var furthest := 0.0
	for i in 200:
		sm.step()
		sm.world.events.clear()
		furthest = maxf(furthest, pat.position.distance_to(start))
	assert_float(furthest).is_greater(150.0)  # reaches the far waypoint (-422, 627)


func test_starslayer_powers_up_after_trigger_delay() -> void:
	var ss: SimUnit = _by_brain("mc2_01_Starslayer")[0]
	sm.world.flags["Starslayer_Trigger"] = true
	_run(3.0)
	assert_int(ss.status).is_equal(SimUnit.Status.SHUTDOWN)
	_run(5.0)
	assert_int(ss.status).is_equal(SimUnit.Status.NORMAL)
	assert_bool(ss.brain.state in ["patrol", "attack"]).is_true()


func test_hangar_damage_springs_infantry_ambush() -> void:
	var hangar := sm.structure_near(Vector2(3221.333, -277.333))
	hangar.take_hit(sm.world.rules, sm.world.rng, 1.0, 0, 143, 0.0)
	_run(1.0)
	assert_bool(sm.world.flags.get("HangarAttacked", false)).is_true()
	var inf: SimUnit = _by_brain("mc2_01_infantry_ambush")[0]
	assert_str(inf.brain.state).is_equal("ambush")


func test_player_returns_fire_when_idle() -> void:
	var player: SimUnit = _by_brain("PBrain")[0]
	var enemy: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	player.last_attacker = enemy
	player.last_attacked_time = 0.05
	_run(0.2)
	assert_int(player.order).is_equal(SimWorld.Order.ATTACK)
	assert_object(player.order_target).is_same(enemy)
