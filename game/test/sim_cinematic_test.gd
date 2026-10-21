extends GdUnitTestSuite
## I12, mc2_17's opening cinematic: the player lance starts ~80 m from the Liao son's camera
## dummy (a team 1 Cyclops) and must leave it alone until the scripted betrayal.
## - pbrain's FireAtWill (orders.abx:2418) is the player lance's only fire at will. pbrain sets
##   SetNotTargetingMod(0.0) (pbrain.abl:110), so contactActionRating rates an enemy that is
##   targeting nobody at 0 (orders.abx:1115-1117) and selectTarget skips it: idle units are left
##   alone, units that are fighting are engaged. The world adds no nearest-enemy fallback of its own.
## - forceMovieEnd is a query (has the player pressed Esc?), it must not end movie mode.

var sm: SimMission


func before_test() -> void:
	sm = SimMission.load_mission(GameData, "mc2_17", 2)


func _by_brain(name: String) -> Array:
	return sm.world.units.filter(func(u): return u.brain_name == name)


## Steps the mission; returns the shots fired by the player team.
func _run(seconds: float) -> Array:
	var shots := []
	for i in int(seconds / SimWorld.TICK):
		sm.step()
		for e in sm.world.events:
			if e["type"] == "shot" and sm.world.units[e["from"]].team == sm.player_team:
				shots.append(e)
		sm.world.events.clear()
	return shots


func test_lance_leaves_the_idle_camera_dummy_alone() -> void:
	var dummy: SimUnit = _by_brain("mc2_17_CamDum_son")[0]
	var lance := _by_brain("PBrain")
	assert_int(lance.size()).is_equal(5)
	assert_int(dummy.team).is_not_equal(sm.player_team)
	var nearest := INF
	for u in lance:
		nearest = minf(nearest, u.distance_to(dummy.position))
	assert_float(nearest).is_less(sm.world.attack_range(lance[0]))  # in weapon reach
	var shots := _run(8.0)
	assert_array(shots).is_empty()
	for u in lance:
		assert_object(u.current_target).is_null()
	assert_array(sm.abl.runtime.errors).is_empty()


func test_lance_engages_an_enemy_that_is_fighting() -> void:
	var dummy: SimUnit = _by_brain("mc2_17_CamDum_son")[0]
	var lance := _by_brain("PBrain")
	_run(1.0)
	# the dummy now targets one of the player's side: rated > 0, FireAtWill selects it
	dummy.current_target = lance[0]
	var shots := _run(3.0)
	assert_array(shots).is_not_empty()
	assert_int(shots[0]["to"]).is_equal(dummy.id)


func test_force_movie_end_is_a_query() -> void:
	_run(5.0)  # the script polls forceMovieEnd every tick from t=3 (mc2_17.abl:1068)
	assert_bool(sm.world.movie_mode).is_true()
	sm.world.force_movie_end = true  # Esc during the cinematic (missiongui.cpp:435-436)
	_run(3.0)
	# the script's own skip path: fade, remove the dummies, endMovieMode (mc2_17.abl:753-790)
	assert_bool(sm.world.movie_mode).is_false()
	assert_bool(_by_brain("mc2_17_CamDum_son")[0].exists).is_false()
