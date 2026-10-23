extends SceneTree
## Group order probe (formation issue, 2026-10-24): 4 lance mechs from one spot, one attack
## order on an enemy group 400 m away (and one group move order), on a flat test map, or on mc2_01's
## ground by the player start (--map). Prints spacing, who fired and damage shares.
##   godot --headless --path game -s res://tools/formation_probe.gd -- [--map] [--seed=N]

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var seed_value := 1
	for a in args:
		if a.begins_with("--seed="):
			seed_value = int(a.substr(7))
	var rules := SimRules.from_data(data)
	var flat := not ("--map" in args)
	var map: SimMap = _flat_map(80) if flat else SimMap.load_mission("mc2_01")
	var origin := Vector2(0, -250) if flat else map.nearest_walkable(Vector2(499.2, -380.0))
	var w := SimWorld.new(rules, map, seed_value)
	var lance: Array = []
	var chassis := ["bushwacker", "shootist", "catapult", "hunchback"]
	for i in 4:
		var m := SimMech.from_chassis(data.chassis[chassis[i]], 0, rules, SimPilot.make(60, 50))
		m.model = chassis[i]
		m.team = 0
		m.is_player = true
		m.commander = 0
		m.group = 0
		m.position = map.nearest_walkable(origin + Vector2(i * 6.0, 0))
		w.add_unit(m)
		lance.append(m)
	var enemies: Array = []
	var dir := Vector2(0, 1)
	var far := map.nearest_walkable(origin + dir * 400.0)
	for i in 3:
		var e := SimMech.from_chassis(data.chassis["bushwacker"], 0, rules, SimPilot.make(50, 50))
		e.model = "bushwacker"
		e.team = 1
		e.position = map.nearest_walkable(far + Vector2(i * 20.0 - 20.0, 0))
		e.facing = 180.0
		w.add_unit(e)
		enemies.append(e)
	var taken := {}
	var fired := {}
	for m in lance:
		w.order_attack(m, enemies[0])
	var t := 0.0
	while t < 90.0:
		w.step()
		t += SimWorld.TICK
		for e in w.events:
			if e["type"] == "shot" and lance.has(w.units[e["from"]]) and t <= 45.0:
				fired[e["from"]] = true
			if e["type"] == "impact" and lance.has(w.units[e["unit"]]):
				taken[e["unit"]] = float(taken.get(e["unit"], 0.0)) + float(e["damage"])
		w.events.clear()
		if abs(t - 45.0) < 0.05:
			_report(w, lance, "attack t=45", fired, taken, enemies[0])
	_report(w, lance, "attack t=90", fired, taken, enemies[0])
	# group move order on a fresh lance position set
	var goal := map.nearest_walkable(origin + Vector2(150, -100))
	var goals: Array = w.group_move_goals(goal, lance.size()) if w.has_method("group_move_goals") else []
	for i in lance.size():
		var m: SimUnit = lance[i]
		if m.is_disabled():
			continue
		w.order_move(m, goals[i] if i < goals.size() else goal)
	for k in 400:
		w.step()
		w.events.clear()
	_report(w, lance, "move", {}, {}, null)
	quit()


func _report(w: SimWorld, lance: Array, label: String, fired: Dictionary, taken: Dictionary, target: SimUnit) -> void:
	var min_sep := INF
	var pairs := 0
	for i in lance.size():
		for j in range(i + 1, lance.size()):
			min_sep = minf(min_sep, lance[i].position.distance_to(lance[j].position))
	var los := 0
	if target:
		for m in lance:
			if w.line_of_sight(m, target):
				los += 1
	var shares := []
	var total := 0.0
	for m in lance:
		total += float(taken.get(m.id, 0.0))
	for m in lance:
		shares.append("%.0f%%" % (100.0 * float(taken.get(m.id, 0.0)) / maxf(total, 1.0)))
	print("%-12s min spacing %.1f m; fired in 45 s %d/4; LOS now %d/4; damage taken %.0f shared %s; disabled %d; positions %s" % [label,
		min_sep, fired.size(), los, total, shares, lance.filter(func(m): return m.is_disabled()).size(),
		lance.map(func(m): return "(%.0f,%.0f)" % [m.position.x, m.position.y])])


static func _flat_map(vps: int) -> SimMap:
	var m := SimMap.new()
	m.meta = {"cell_bits": {"terrain": [0, 15], "overlay": [4, 3], "gate": [8, 1], "offmap": [9, 1], "passable": [10, 1],
		"mine": [13, 15], "height": [18, 15], "wall": [24, 1], "road": [25, 1], "shallow": [26, 1], "deep": [27, 1], "forest": [28, 1]}}
	m.vertices_per_side = vps
	m.cells_per_side = vps * 3
	m.vertex_m = 25.6
	m.cell_m = 25.6 / 3.0
	m.half_m = vps * 25.6 / 2.0
	m.elevation_m.resize(vps * vps)
	m.elevation_m.fill(0.0)
	m.cells.resize(m.cells_per_side * m.cells_per_side)
	m.cells.fill(1 << 10)
	m.mines.resize(m.cells.size())
	return m
