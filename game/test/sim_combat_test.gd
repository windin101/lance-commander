extends GdUnitTestSuite
## Combat rules against hand-checked cases from the original code
## (docs/specs/combat-rules.md).

const B := SimMech.Body
const A := SimMech.Armor
const ER_LASER := 143
const LRM5 := 120
const STREAK2 := 125
const LRM_AMMO := 220

var r: SimRules


func before_test() -> void:
	r = SimFixture.rules()


# --- building -------------------------------------------------------------

func test_atlas_prime_build() -> void:
	var m := SimFixture.mech("atlas", r)
	assert_str(m.variant_name).is_equal("Atlas Prime")
	assert_float(m.internal[B.CTORSO]).is_equal(31.0)
	# 7 armour plates x 32 points spread by share (mech.cpp:1879)
	assert_float(m.max_armor[A.CTORSO]).is_equal_approx(11.0 + 0.17 * 224.0, 0.001)
	assert_float(m.max_armor[A.LARM]).is_equal_approx(8.0 + 0.12 * 224.0, 0.001)
	assert_float(m.armor[A.HEAD]).is_equal(9.0)
	assert_int(m.cockpit).is_greater_equal(0)
	assert_int(m.engine).is_greater_equal(0)
	assert_int(m.hip_actuators.size()).is_equal(2)
	# 4 ER lasers, 4 LRM5, 4 Streak SRM2, AC20, 3 MG arrays
	assert_int(m.num_weapons).is_equal(16)
	assert_int(m.weapon_shots(SimFixture.item(m, LRM5))).is_equal(96)


# --- to-hit ---------------------------------------------------------------

func test_base_chance_is_gunnery_at_medium_difficulty() -> void:
	var d := SimFixture.duel(r)
	assert_float(SimCombat.attack_chance(r, d[0], SimFixture.item(d[0], ER_LASER), d[1])).is_equal(60.0)


func test_range_limits_use_cell_diagonal_tolerance() -> void:
	var d := SimFixture.duel(r, 140.0)  # medium long range 120 + 12.07
	var laser := SimFixture.item(d[0], ER_LASER)
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(SimCombat.NO_SHOT)
	d[1].position = Vector2(0, 131.0)
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(60.0)
	d[1].position = Vector2(0, 17.0)  # medium min 30 - 12.07
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(SimCombat.NO_SHOT)


func test_clamped_to_95_and_disabled_target_is_100() -> void:
	r.difficulty = 0  # player skills 125%
	var d := SimFixture.duel(r)
	d[0].pilot.gunnery = 90.0
	var laser := SimFixture.item(d[0], ER_LASER)
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(95.0)
	d[1].status = SimMech.Status.DISABLED
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(100.0)


func test_enemy_difficulty_fix_flag() -> void:
	r.difficulty = 3  # enemy skills 150%
	var d := SimFixture.duel(r)
	d[0].is_player = false
	var laser := SimFixture.item(d[0], ER_LASER)
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(90.0)
	r.fix_enemy_difficulty = false  # original bug: enemies unmodified
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(60.0)


func test_aimed_head_shot_and_sharpshooter() -> void:
	var d := SimFixture.duel(r)
	var laser := SimFixture.item(d[0], ER_LASER)
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1], B.HEAD)).is_equal(5.0)  # 60 x 0.08 = 4.8
	d[0].pilot.specialties["SharpShooter"] = true
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1], B.LLEG)).is_equal_approx(60.0 * 0.2 + 20.0, 0.001)


func test_specialties() -> void:
	var d := SimFixture.duel(r)
	var laser := SimFixture.item(d[0], ER_LASER)
	d[0].pilot.specialties["ERLaserSpecialist"] = true
	d[0].pilot.specialties["MediumRangeSpecialist"] = true
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(95.0)  # 60 + 20 + 15
	d[1].pilot.specialties["AssaultMechSpecialist"] = true  # 100 t is outside 80-99: no effect
	assert_float(SimCombat.attack_chance(r, d[0], laser, d[1])).is_equal(95.0)


func test_heat_fire_penalty() -> void:
	var d := SimFixture.duel(r)
	d[0].heat = d[0].heat_capacity * 10.0 / 30.0 + 0.01  # level 10: fire_mod 23
	assert_float(SimCombat.attack_chance(r, d[0], SimFixture.item(d[0], ER_LASER), d[1])).is_equal(37.0)
	r.heat_enabled = false
	assert_float(SimCombat.attack_chance(r, d[0], SimFixture.item(d[0], ER_LASER), d[1])).is_equal(60.0)


# --- hit location ---------------------------------------------------------

func test_hit_location_arcs() -> void:
	var t := SimFixture.mech("atlas", r)  # at origin, facing north
	var rng := SimRng.new()
	rng.force([0, 2, 29, 17, 50])
	assert_int(SimCombat.hit_location(r, rng, t, Vector2(0, 100))).is_equal(A.HEAD)  # front: 2 head
	assert_int(SimCombat.hit_location(r, rng, t, Vector2(0, 100))).is_equal(A.CTORSO)
	assert_int(SimCombat.hit_location(r, rng, t, Vector2(100, 0))).is_equal(A.RTORSO)  # right arc
	assert_int(SimCombat.hit_location(r, rng, t, Vector2(-100, 0))).is_equal(A.LTORSO)  # left arc
	assert_int(SimCombat.hit_location(r, rng, t, Vector2(0, -100))).is_equal(A.RCTORSO)  # rear


# --- damage ---------------------------------------------------------------

func test_armor_absorbs_damage() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	SimCombat.handle_weapon_hit(r, rng, m, 10.0, A.LARM, ER_LASER, 0.0)
	assert_float(m.armor[A.LARM]).is_equal_approx(24.88, 0.001)
	assert_float(m.internal[B.LARM]).is_equal(17.0)


func test_holed_armor_damages_internal_and_rolls_crits() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	rng.force([0])  # crit roll < 58: none
	m.armor[A.LARM] = 2.0
	SimCombat.handle_weapon_hit(r, rng, m, 5.0, A.LARM, ER_LASER, 0.0)
	assert_float(m.armor[A.LARM]).is_equal(0.0)
	assert_float(m.internal[B.LARM]).is_equal(14.0)
	assert_int(rng.forced_remaining()).is_equal(0)


func test_destroyed_arm_transfers_to_side_torso_front_armor() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	m.armor[A.LARM] = 0.0
	m.internal[B.LARM] = 1.0
	SimCombat.handle_weapon_hit(r, rng, m, 6.0, A.LARM, ER_LASER, 0.0)
	assert_int(m.damage_state[B.LARM]).is_equal(SimMech.DamageState.DESTROYED)
	assert_float(m.armor[A.LTORSO]).is_equal_approx(37.0 - 5.0, 0.001)
	assert_bool(m.items[SimFixture.item(m, ER_LASER)]["disabled"]).is_true()


func test_ammo_crit_does_not_explode() -> void:
	# Shipped MC2: a destroyed ammo bin does nothing (mech.cpp hitInventoryItem;
	# Mover::ammoExplosion is never called). The bin is just disabled.
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	var bin := SimFixture.item(m, LRM_AMMO)
	SimCombat.hit_inventory_item(r, rng, m, bin, 0.0)
	assert_bool(m.items[bin]["disabled"]).is_true()
	assert_int(m.damage_state[B.LTORSO]).is_equal(SimMech.DamageState.NONE)
	assert_float(m.pilot.wounds).is_equal(0.0)
	assert_bool(m.is_disabled()).is_false()


func test_engine_crit_disables() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	rng.force([60, 0])  # one crit, first CT slot = Fusion Engine
	m.armor[A.CTORSO] = 0.0
	SimCombat.handle_weapon_hit(r, rng, m, 5.0, A.CTORSO, ER_LASER, 0.0)
	assert_bool(m.items[m.engine]["disabled"]).is_true()
	assert_int(m.status).is_equal(SimMech.Status.DISABLED)


func test_cockpit_crit_only_wounds_from_the_head_hit() -> void:
	# A destroyed cockpit is only a damage effect in the shipped game; the pilot takes
	# just the head-hit wound (damage >= 2 to the head).
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	rng.force([60, 0])  # one crit, first head slot = Cockpit
	SimCombat.handle_weapon_hit(r, rng, m, 10.0, A.HEAD, ER_LASER, 0.0)  # 9 armour, 1 internal
	assert_float(m.internal[B.HEAD]).is_equal(2.0)
	assert_bool(m.items[m.cockpit]["disabled"]).is_true()
	assert_float(m.pilot.wounds).is_equal(1.0)
	assert_bool(m.pilot.dead).is_false()
	assert_int(m.status).is_equal(SimMech.Status.NORMAL)


func test_top_crit_roll_blows_off_limb_but_triple_crits_torso() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	rng.force([97])
	m.armor[A.RARM] = 0.0
	SimCombat.handle_weapon_hit(r, rng, m, 1.0, A.RARM, ER_LASER, 0.0)
	assert_int(m.damage_state[B.RARM]).is_equal(SimMech.DamageState.DESTROYED)
	rng.force([97, 0, 0, 0])  # 3 crits into the left torso's first slot (LRM5)
	m.armor[A.LTORSO] = 0.0
	SimCombat.handle_weapon_hit(r, rng, m, 1.0, A.LTORSO, ER_LASER, 0.0)
	assert_int(m.damage_state[B.LTORSO]).is_equal(SimMech.DamageState.NONE)
	assert_bool(m.items[SimFixture.item(m, LRM5)]["disabled"]).is_true()
	assert_int(rng.forced_remaining()).is_equal(0)


func test_center_torso_destroyed_at_once_explodes_else_shuts_down() -> void:
	var m := SimFixture.mech("atlas", r)
	var rng := SimRng.new()
	m.armor[A.CTORSO] = 0.0
	SimCombat.handle_weapon_hit(r, rng, m, 40.0, A.CTORSO, ER_LASER, 3.0)
	assert_int(m.status).is_equal(SimMech.Status.DESTROYED)
	# Destroying the CT crits its engine (blow time = now + 5), so a CT kill
	# explodes unless the engine was wrecked more than 5 s earlier.
	var m2 := SimFixture.mech("atlas", r)
	m2.armor[A.CTORSO] = 0.0
	rng.force([60, 0])  # t=0: one crit on the engine -> disabled, blow time 5
	SimCombat.handle_weapon_hit(r, rng, m2, 5.0, A.CTORSO, ER_LASER, 0.0)
	assert_int(m2.status).is_equal(SimMech.Status.DISABLED)
	SimCombat.handle_weapon_hit(r, rng, m2, 40.0, A.CTORSO, ER_LASER, 10.0)
	assert_int(m2.damage_state[B.CTORSO]).is_equal(SimMech.DamageState.DESTROYED)
	assert_int(m2.status).is_equal(SimMech.Status.DISABLED)


# --- firing ---------------------------------------------------------------

func test_fire_hit_sets_recycle_heat_and_location() -> void:
	var d := SimFixture.duel(r)
	var rng := SimRng.new()
	var laser := SimFixture.item(d[0], ER_LASER)
	rng.force([10, 2])  # hit roll, then location roll -> CT (middle front)
	var shot := SimCombat.fire_weapon(r, rng, d[0], laser, d[1], 5.0)
	assert_bool(shot["hit"]).is_true()
	assert_int(shot["location"]).is_equal(A.CTORSO)
	assert_float(shot["damage"]).is_equal(2.5)
	assert_float(d[0].items[laser]["ready_time"]).is_equal_approx(9.2, 0.001)
	assert_float(d[0].heat).is_equal(5.0)
	assert_str(SimCombat.fire_weapon(r, rng, d[0], laser, d[1], 6.0)["reason"]).is_equal("not_ready")
	SimCombat.apply_shot(r, rng, d[1], shot, 5.0)
	assert_float(d[1].armor[A.CTORSO]).is_equal_approx(49.08 - 2.5, 0.001)


func test_misses_spend_ammo_except_streaks() -> void:
	var d := SimFixture.duel(r)
	var rng := SimRng.new()
	rng.force([99, 99])
	var lrm := SimFixture.item(d[0], LRM5)
	var streak := SimFixture.item(d[0], STREAK2)
	var streak_before: int = d[0].weapon_shots(streak)
	assert_bool(SimCombat.fire_weapon(r, rng, d[0], lrm, d[1], 0.0)["hit"]).is_false()
	assert_int(d[0].weapon_shots(lrm)).is_equal(95)
	assert_bool(SimCombat.fire_weapon(r, rng, d[0], streak, d[1], 0.0)["fired"]).is_true()
	assert_int(d[0].weapon_shots(streak)).is_equal(streak_before)


func test_shutdown_mech_cannot_fire() -> void:
	var d := SimFixture.duel(r)
	d[0].status = SimMech.Status.SHUTDOWN
	var shot := SimCombat.fire_weapon(r, SimRng.new(), d[0], SimFixture.item(d[0], ER_LASER), d[1], 0.0)
	assert_str(shot["reason"]).is_equal("not_operational")
