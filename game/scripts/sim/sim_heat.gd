class_name SimHeat
extends RefCounted
## Heat (docs/specs/combat-rules.md H1-H8). The original's updateHeat was
## compiled out and unfinished; this completes it with the original's tables.


## Advance one mech's heat by dt seconds. Weapon heat is added at fire time
## by SimCombat.fire_weapon (H3).
static func update(rules: SimRules, rng: SimRng, m: SimMech, dt: float, now: float) -> void:
	if not rules.heat_enabled or m.is_destroyed():
		return
	var h: Dictionary = rules.heat
	var change := 0.0
	if not m.is_disabled() and m.status != SimMech.Status.SHUTDOWN:
		var per_level := m.heat_capacity / 30.0
		var state_heat: Array = h["body_state_heat"]
		change += float(state_heat[m.body_state]) * per_level * dt
	change -= dissipation(rules, m) * dt
	m.heat = maxf(0.0, m.heat + change)

	if now < m.heat_check_time:
		return
	m.heat_check_time = now + float(h["check_frequency"])
	if m.is_disabled():
		return
	var level := m.heat_level()
	var row := rules.heat_row(level)
	if m.status == SimMech.Status.SHUTDOWN:
		if level <= int(h["restart_level"]):
			m.status = SimMech.Status.NORMAL
		return
	if level >= int(h["shutdown_level"]) or rng.roll(100) < float(row["shutdown_pct"]):
		m.status = SimMech.Status.SHUTDOWN
	if float(row["ammo_explosion_pct"]) > 0.0 and rng.roll(100) < float(row["ammo_explosion_pct"]):
		var bins: Array[int] = []
		for i in range(m.num_other + m.num_weapons, m.items.size()):
			if not m.items[i]["disabled"] and m.items[i]["amount"] > 0:
				bins.append(i)
		if not bins.is_empty():
			var inv: int = bins[rng.roll(bins.size())]
			m.items[inv]["disabled"] = true
			m.items[inv]["health"] = 0
			SimCombat.ammo_explosion(rules, rng, m, inv, now)
	if m.life_support >= 0 and m.items[m.life_support]["disabled"] and int(row["injuries"]) > 0:
		SimCombat._injure_pilot(m, float(row["injuries"]))


## Heat shed per second: the base rate plus working heat sinks (H5).
static func dissipation(rules: SimRules, m: SimMech) -> float:
	var total := float(rules.heat["dissipation_rate"]) * m.heat_capacity
	for i in m.num_other:
		var item := m.items[i]
		if item["form"] == "HeatSink" and not item["disabled"]:
			total += float(item["component"]["heatsink"]["dissipation"])
	return total * float(rules.heat["sink_efficiency"])


## Speed multiplier from the heat table's move_mod (H8).
static func speed_factor(rules: SimRules, m: SimMech) -> float:
	return clampf(1.0 - float(rules.heat_row(m.heat_level())["move_mod"]) / 200.0, 0.0, 1.0)
