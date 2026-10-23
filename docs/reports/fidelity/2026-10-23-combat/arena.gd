extends SceneTree
## Fidelity arena: a 4-mech lance against a vehicle group on open ground, no brains, no bot.
## args: <runs> <enemy spec e.g. partisan:4,lrmcarrier:2,catapult:2> <distance m> [heatoff] [nodes] [gunnery=N]

var data

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var runs := int(args[0]) if args.size() > 0 else 40
	var spec := String(args[1]) if args.size() > 1 else "partisan:4"
	var dist := float(args[2]) if args.size() > 2 else 150.0
	var heatoff := "heatoff" in args
	var nodes := "nodes" in args
	var pursue := "pursue" in args
	var gun := 75.0
	for a in args:
		if String(a).begins_with("gunnery="):
			gun = float(String(a).split("=")[1])
	data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var map := SimMap.load_mission("mc2_01")
	var rules := SimRules.from_data(data)
	rules.heat_enabled = not heatoff
	var origin := Vector2(500, -250)
	var agg := {"l_shots": 0, "l_hits": 0, "e_shots": 0, "e_hits": 0, "l_dmg": 0.0, "e_dmg": 0.0, "t": 0.0,
		"l_alive": 0, "e_alive": 0, "first_l_loss": 0.0, "first_l_loss_n": 0, "lance_win": 0, "heat_sum": 0.0, "heat_n": 0}
	var lance_names := ["madcat", "madcat", "shootist", "catapult"]
	for run in runs:
		var w := SimWorld.new(rules, map, run + 101)
		var lance: Array = []
		var foes: Array = []
		for i in lance_names.size():
			var m := SimMech.from_chassis(data.chassis[lance_names[i]], 0, rules, SimPilot.make(gun, 70))
			m.position = origin + Vector2(i * 25.0 - 37.5, 0)
			m.team = 0
			m.is_player = true
			w.add_unit(m)
			lance.append(m)
		var k := 0
		for part in spec.split(","):
			var bits := part.split(":")
			var name := bits[0]
			var n := int(bits[1])
			for j in n:
				var u: SimUnit
				var p := SimPilot.make(55, 5)
				if data.chassis.has(name):
					u = SimMech.from_chassis(data.chassis[name], 0, rules, p)
				else:
					u = SimVehicle.from_data(JSON.parse_string(FileAccess.get_file_as_string("res://data/vehicles/%s.json" % name)), rules, p)
				u.position = origin + Vector2(k * 25.0 - 50.0, dist)
				u.facing = 180.0
				u.team = 1
				w.add_unit(u)
				foes.append(u)
				k += 1
		var node_units := {}
		if nodes:
			for u in foes:
				if u is SimVehicle and u.model in ["partisan", "legion"]:
					var ws: Array = u.weapon_indices()
					for i in ws.size():
						if i >= 2:
							u.items[ws[i]]["ready_time"] = INF
					node_units[u.id] = true
		var first_loss := -1.0
		while w.time < 300.0:
			# orders: lance focus-fires the nearest live foe; foes all attack the nearest live lance mech
			var live_l := lance.filter(func(x): return not x.is_disabled())
			var live_e := foes.filter(func(x): return not x.is_disabled())
			if live_l.is_empty() or live_e.is_empty():
				break
			if int(round(w.time * 10.0)) % 10 == 0:
				var tgt: SimUnit = live_e[0]
				for e in live_e:
					if e.position.distance_to(origin) < tgt.position.distance_to(origin):
						tgt = e
				for m in live_l:
					if m.order_target != tgt:
						w.order_attack(m, tgt, true, pursue)
				for e in live_e:
					var best: SimUnit = live_l[0]
					for m in live_l:
						if m.position.distance_to(e.position) < best.position.distance_to(e.position):
							best = m
					if e.order_target != best:
						w.order_attack(e, best, true, pursue)
			w.step()
			for ev in w.events:
				if ev["type"] == "shot":
					var a: SimUnit = w.units[ev["from"]]
					if a.team == 0:
						agg["l_shots"] += 1
						agg["l_hits"] += int(ev["hit"])
						agg["heat_sum"] += a.heat_level()
						agg["heat_n"] += 1
					else:
						agg["e_shots"] += 1
						agg["e_hits"] += int(ev["hit"])
						if node_units.has(a.id):
							a.items[int(ev["weapon"])]["ready_time"] = INF
				elif ev["type"] == "impact":
					var from := int(ev.get("from", -1))
					if from >= 0:
						if w.units[from].team == 0:
							agg["l_dmg"] += float(ev["damage"])
						else:
							agg["e_dmg"] += float(ev["damage"])
				elif ev["type"] == "disabled" and w.units[ev["unit"]].team == 0 and first_loss < 0.0:
					first_loss = w.time
			w.events.clear()
		agg["t"] += w.time
		var la := lance.filter(func(x): return not x.is_disabled()).size()
		var ea := foes.filter(func(x): return not x.is_disabled()).size()
		agg["l_alive"] += la
		agg["e_alive"] += ea
		agg["lance_win"] += int(ea == 0 and la > 0)
		if first_loss >= 0.0:
			agg["first_l_loss"] += first_loss
			agg["first_l_loss_n"] += 1
	var mins: float = agg["t"] / 60.0
	print("ARENA %s vs lance(madcat x2, shootist, catapult; gunnery %.0f) at %.0f m, heat %s, node rule %s, pursue %s, %d runs" % [spec, gun, dist, "off" if heatoff else "on", "on" if nodes else "off", pursue, runs])
	print("  lance: hit rate %.2f (%d shots), %.0f dmg/min, mean heat level at fire %.1f" % [float(agg["l_hits"]) / maxf(agg["l_shots"], 1), agg["l_shots"], agg["l_dmg"] / mins, agg["heat_sum"] / maxf(agg["heat_n"], 1)])
	print("  enemy: hit rate %.2f (%d shots), %.0f dmg/min" % [float(agg["e_hits"]) / maxf(agg["e_shots"], 1), agg["e_shots"], agg["e_dmg"] / mins])
	print("  mean fight %.0f s; lance wins %d/%d; lance alive %.2f/4; enemy alive %.2f; first lance loss at %s s (%d runs)" % [agg["t"] / runs, agg["lance_win"], runs,
		float(agg["l_alive"]) / runs, float(agg["e_alive"]) / runs,
		("%.0f" % (agg["first_l_loss"] / agg["first_l_loss_n"])) if agg["first_l_loss_n"] > 0 else "-", agg["first_l_loss_n"]])
	data.free()
	quit()
