extends SceneTree
## Headless duel runner for rules sanity checks and heat tuning.
## godot --headless --path game -s res://tools/duel_cli.gd -- atlas madcat [runs] [distance] [no-heat]
## Each mech fires every ready weapon each 0.25 s combat tick (CombatUpdateFrequency).

const TICK := 0.25
const MAX_TIME := 300.0


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var a_name := args[0] if args.size() > 0 else "atlas"
	var b_name := args[1] if args.size() > 1 else "madcat"
	var runs := int(args[2]) if args.size() > 2 else 200
	var distance := float(args[3]) if args.size() > 3 else 90.0
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var rules := SimRules.from_data(data)
	rules.heat_enabled = not ("no-heat" in args)

	var wins := {"a": 0, "b": 0, "draw": 0}
	var total_time := 0.0
	var shutdown_ticks := [0, 0]
	var ticks := 0
	for run in runs:
		var rng := SimRng.new(run + 1)
		var a := SimMech.from_chassis(data.chassis[a_name], 0, rules, SimPilot.make(60, 60))
		var b := SimMech.from_chassis(data.chassis[b_name], 0, rules, SimPilot.make(60, 60))
		a.is_player = true
		b.position = Vector2(0, distance)
		b.facing = 180.0
		var t := 0.0
		while t < MAX_TIME and not a.is_disabled() and not b.is_disabled():
			for pair in [[a, b], [b, a]]:
				var shooter: SimMech = pair[0]
				var target: SimMech = pair[1]
				for w in shooter.weapon_indices():
					var shot := SimCombat.fire_weapon(rules, rng, shooter, w, target, t)
					SimCombat.apply_shot(rules, rng, target, shot, t)
			SimHeat.update(rules, rng, a, TICK, t)
			SimHeat.update(rules, rng, b, TICK, t)
			shutdown_ticks[0] += int(a.status == SimMech.Status.SHUTDOWN)
			shutdown_ticks[1] += int(b.status == SimMech.Status.SHUTDOWN)
			ticks += 1
			t += TICK
		total_time += t
		if a.is_disabled() and b.is_disabled():
			wins["draw"] += 1
		elif b.is_disabled():
			wins["a"] += 1
		elif a.is_disabled():
			wins["b"] += 1
		else:
			wins["draw"] += 1
	print("%s vs %s at %.0f m, %d runs, heat %s" % [a_name, b_name, distance, runs, "on" if rules.heat_enabled else "off"])
	print("  wins: %s %d, %s %d, draws %d" % [a_name, wins["a"], b_name, wins["b"], wins["draw"]])
	print("  mean fight length: %.1f s" % (total_time / runs))
	print("  time shut down: %s %.0f%%, %s %.0f%%" % [a_name, 100.0 * shutdown_ticks[0] / ticks, b_name, 100.0 * shutdown_ticks[1] / ticks])
	data.free()
	quit()
