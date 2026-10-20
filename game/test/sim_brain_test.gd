extends GdUnitTestSuite
## mc2_01 AI on the mission's original ABL (SimAbl): guards intercept, the airfield
## objective starts patrols, the Starslayer wakes on its trigger, hangar damage
## springs the infantry ambush. The player lance runs pbrain: its alarm handlers
## return fire, and player orders reach it as tactical orders with player origin.

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
	assert_int(sm.abl.pilots.size()).is_equal(29)
	assert_array(sm.abl.runtime.errors).is_empty()
	for u in _by_brain("PBrain"):
		assert_bool(u.brain is SimAbl.Pilot).is_true()
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


func _shot(from: SimUnit, to: SimUnit) -> void:
	sm.abl.after_step([{"type": "shot", "from": from.id, "to": to.id}])


func test_player_returns_fire_when_idle() -> void:
	# pbrain handleTargetOfWeaponFire: no player order -> orderAttackObject(attacker)
	var player: SimUnit = _by_brain("PBrain")[0]
	var enemy: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	_run(0.2)
	_shot(enemy, player)
	assert_int(player.order).is_equal(SimWorld.Order.ATTACK)
	assert_object(player.order_target).is_same(enemy)
	assert_array(sm.abl.runtime.errors).is_empty()


func test_player_move_order_keeps_moving_and_fires_on_the_move() -> void:
	# A player order wins over the brain: shot at while moving, pbrain only sets the target.
	var player: SimUnit = _by_brain("PBrain")[0]
	var enemy: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	_run(0.2)
	var goal := player.position + Vector2(200, 0)
	sm.abl.player_order(player, "move", goal)
	assert_int(player.brain.order["code"]).is_equal(SimAbl.TO_MOVETO_POINT)
	assert_int(player.brain.order["origin"]).is_equal(0)
	_shot(enemy, player)
	assert_int(player.order).is_equal(SimWorld.Order.MOVE)
	assert_object(player.current_target).is_same(enemy)


func test_stop_clears_the_order() -> void:
	var player: SimUnit = _by_brain("PBrain")[0]
	_run(0.2)
	sm.abl.player_order(player, "move", player.position + Vector2(200, 0))
	sm.abl.player_order(player, "stop")
	assert_int(player.brain.order["code"]).is_equal(SimAbl.TO_NONE)
	assert_int(player.order).is_equal(SimWorld.Order.HOLD)


# --- I82: the palette orders through pbrain ---------------------------------------------

func test_player_move_walks_unless_run() -> void:
	var player: SimUnit = _by_brain("PBrain")[0]
	_run(0.2)
	sm.abl.player_order(player, "move", player.position + Vector2(200, 0))
	assert_bool(player.brain.order["run"]).is_false()
	assert_bool(player.move_run).is_false()
	sm.abl.player_order(player, "move", player.position + Vector2(200, 0), {"run": true})
	assert_bool(player.move_run).is_true()


func test_player_jump_order() -> void:
	var player: SimUnit = _by_brain("PBrain").filter(func(u): return u.can_jump())[0]
	_run(0.2)
	sm.abl.player_order(player, "jump", player.position + Vector2(0, 400))
	assert_int(player.order).is_not_equal(SimWorld.Order.JUMP)  # out of range: refused
	assert_bool(sm.world.events.any(func(e): return e["type"] == "order_refused")).is_true()
	var goal := sm.world.map.nearest_walkable(player.position + Vector2(0, 90))
	sm.abl.player_order(player, "jump", goal)
	assert_int(player.brain.order["code"]).is_equal(SimAbl.TO_JUMPTO_POINT)
	assert_int(player.order).is_equal(SimWorld.Order.JUMP)
	_run(SimWorld.JUMP_TIME + 0.3)
	assert_float(player.position.distance_to(goal)).is_less(0.01)
	assert_int(player.brain.order["code"]).is_equal(SimAbl.TO_NONE)
	assert_array(sm.abl.runtime.errors).is_empty()


func test_player_fire_from_position_and_hold_position_do_not_pursue() -> void:
	var player: SimUnit = _by_brain("PBrain")[0]
	var enemy: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	_run(0.2)
	sm.abl.player_order(player, "attack", enemy, {"pursue": false})
	assert_int(player.order).is_equal(SimWorld.Order.ATTACK)
	assert_bool(player.attack_pursue).is_false()
	assert_bool(player.brain.order["pursue"]).is_false()
	player.hold_position = true
	sm.abl.player_order(player, "attack", enemy)
	assert_bool(player.attack_pursue).is_false()


func test_player_guard_point_runs_through_pbrain() -> void:
	# pbrain KludgeHandleGuard: getTacOrder -> Sentry(point): engage what comes near (orders.abi:1509)
	var player: SimUnit = _by_brain("PBrain")[0]
	var enemy: SimUnit = _by_brain("mc2_01_Pat1_1")[0]
	_run(0.2)
	var post := player.position
	sm.abl.player_order(player, "guard", post)
	assert_int(player.brain.order["code"]).is_equal(SimAbl.TO_GUARD)
	assert_int(player.order).is_equal(SimWorld.Order.GUARD)
	enemy.position = sm.world.map.nearest_walkable(post + Vector2(0, 180))
	_run(6.0)
	assert_object(player.current_target).is_same(enemy)
	# the brain took the guard over: its own attack order (Fight: orderAttackContact), not ours
	assert_int(player.brain.order["code"]).is_equal(SimAbl.TO_ATTACK_OBJECT)
	assert_int(int(player.brain.order["origin"])).is_not_equal(0)
	assert_float(player.position.distance_to(post)).is_less(SimWorld.GUARD_DISENGAGE_M)
	assert_array(sm.abl.runtime.errors).is_empty()
