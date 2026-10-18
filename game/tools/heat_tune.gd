extends SceneTree
## Heat tuning with the real SimWorld combat loop (fire discipline included).
## godot --headless --path game -s res://tools/heat_tune.gd -- <a> <b> <runs> <distance> <dissipation_rate> [no-heat]

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var a_name := args[0] if args.size() > 0 else "atlas"
	var b_name := args[1] if args.size() > 1 else "madcat"
	var runs := int(args[2]) if args.size() > 2 else 60
	var dist := float(args[3]) if args.size() > 3 else 90.0
	var rate := float(args[4]) if args.size() > 4 else 0.12
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var map := SimMap.load_mission("mc2_01")
	var rules := SimRules.from_data(data)
	rules.heat["dissipation_rate"] = rate
	rules.heat_enabled = not ("no-heat" in args)
	var origin := Vector2(500, -250)
	var wins := [0, 0, 0]
	var total_t := 0.0
	var sd := [0, 0]
	var ticks := 0
	var peak := [0, 0]
	for run in runs:
		var w := SimWorld.new(rules, map, run + 1)
		var a := SimMech.from_chassis(data.chassis[a_name], 0, rules, SimPilot.make(60, 60))
		var b := SimMech.from_chassis(data.chassis[b_name], 0, rules, SimPilot.make(60, 60))
		a.position = origin
		a.team = 0
		a.is_player = true
		b.position = origin + Vector2(0, dist)
		b.facing = 180.0
		b.team = 1
		w.add_unit(a)
		w.add_unit(b)
		w.order_attack(a, b)
		w.order_attack(b, a)
		while w.time < 300.0 and not a.is_disabled() and not b.is_disabled():
			w.step()
			w.events.clear()
			sd[0] += int(a.status == SimUnit.Status.SHUTDOWN)
			sd[1] += int(b.status == SimUnit.Status.SHUTDOWN)
			peak[0] = maxi(peak[0], a.heat_level())
			peak[1] = maxi(peak[1], b.heat_level())
			ticks += 1
		total_t += w.time
		wins[0 if b.is_disabled() and not a.is_disabled() else (1 if a.is_disabled() and not b.is_disabled() else 2)] += 1
	print("%s v %s %.0fm rate %.2f heat %s: wins %d/%d draws %d, mean %.1fs, shutdown %.1f%%/%.1f%%, peak level %d/%d" % [
		a_name, b_name, dist, rate, "on" if rules.heat_enabled else "off", wins[0], wins[1], wins[2], total_t / runs,
		100.0 * sd[0] / ticks, 100.0 * sd[1] / ticks, peak[0], peak[1]])
	data.free()
	quit()
