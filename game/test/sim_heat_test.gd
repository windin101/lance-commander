extends GdUnitTestSuite
## Heat (docs/specs/combat-rules.md H1-H8).

var r: SimRules


func before_test() -> void:
	r = SimFixture.rules()


func _level_heat(m: SimMech, level: int) -> float:
	return m.heat_capacity * float(level) / 30.0 + 0.001


func test_dissipation_is_capacity_fraction_per_second() -> void:
	var m := SimFixture.mech("atlas", r)  # capacity 43, no heat sinks
	m.heat = 10.0
	SimHeat.update(r, SimRng.new(1), m, 1.0, 0.0)
	assert_float(m.heat).is_equal_approx(10.0 - 0.12 * 43.0, 0.001)


func test_heat_never_goes_negative() -> void:
	var m := SimFixture.mech("atlas", r)
	m.heat = 1.0
	SimHeat.update(r, SimRng.new(1), m, 5.0, 0.0)
	assert_float(m.heat).is_equal(0.0)


func test_running_builds_heat() -> void:
	var m := SimFixture.mech("atlas", r)
	r.heat["dissipation_rate"] = 0.0
	m.body_state = SimMech.BodyState.RUNNING
	SimHeat.update(r, SimRng.new(1), m, 2.0, 0.0)
	assert_float(m.heat).is_equal_approx(0.3 * 43.0 / 30.0 * 2.0, 0.001)


func test_shutdown_at_threshold_then_restart_when_cool() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new(1)
	m.heat = _level_heat(m, 26)
	SimHeat.update(r, rng, m, 0.0, 0.0)
	assert_int(m.status).is_equal(SimMech.Status.SHUTDOWN)
	m.heat = _level_heat(m, 16)
	SimHeat.update(r, rng, m, 0.0, 1.0)
	assert_int(m.status).is_equal(SimMech.Status.SHUTDOWN)
	m.heat = _level_heat(m, 15)
	SimHeat.update(r, rng, m, 0.0, 2.0)
	assert_int(m.status).is_equal(SimMech.Status.NORMAL)


func test_checks_wait_for_frequency() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new(1)
	SimHeat.update(r, rng, m, 0.0, 0.0)  # check at t=0, next at t=1
	m.heat = _level_heat(m, 28)
	SimHeat.update(r, rng, m, 0.0, 0.5)
	assert_int(m.status).is_equal(SimMech.Status.NORMAL)
	SimHeat.update(r, rng, m, 0.0, 1.0)
	assert_int(m.status).is_equal(SimMech.Status.SHUTDOWN)


func test_random_shutdown_from_table() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	m.heat = _level_heat(m, 22)  # shutdown_pct 5.8, ammo 0.8
	rng.force([5, 99])  # 5 < 5.8 -> shut down; ammo roll fails
	SimHeat.update(r, rng, m, 0.0, 0.0)
	assert_int(m.status).is_equal(SimMech.Status.SHUTDOWN)


func test_heat_cooks_off_ammo() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	m.heat = _level_heat(m, 23)  # ammo explosion 2.8%
	rng.force([99, 0, 0])  # no shutdown; ammo roll 0 < 2.8; pick the first bin
	SimHeat.update(r, rng, m, 0.0, 0.0)
	assert_float(m.pilot.wounds).is_greater_equal(2.0)


func test_heat_off_gives_original_behaviour() -> void:
	r.heat_enabled = false
	var m := SimFixture.mech("atlas", r)
	m.heat = _level_heat(m, 29)
	SimHeat.update(r, SimRng.new(1), m, 1.0, 0.0)
	assert_int(m.status).is_equal(SimMech.Status.NORMAL)
	assert_float(SimHeat.speed_factor(r, m)).is_equal(1.0)


func test_speed_factor() -> void:
	var m := SimFixture.mech("atlas", r)
	m.heat = _level_heat(m, 30)  # move_mod 180
	assert_float(SimHeat.speed_factor(r, m)).is_equal_approx(0.1, 0.001)
