extends SceneTree
func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	var args := OS.get_cmdline_user_args()
	var mission := String(args[0]); var cx := int(args[1]); var cy := int(args[2]); var r := int(args[3])
	var sm := SimMission.load_mission(data, mission)
	var map: SimMap = sm.world.map
	var d: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/maps/%s/objects.json" % mission))
	var mark := {}
	for o in d["objects"]:
		var t: Dictionary = d["types"].get(str(int(o["type"])), {})
		var app := String(t.get("appearance", ""))
		var ch := ""
		if "wall" in app: ch = "w"
		elif "post" in app: ch = "p"
		elif "gate" in app and not "control" in app: ch = "G"
		elif "control" in app: ch = "C"
		if ch == "": continue
		var pos := Vector2(float(o["x"]), float(o["y"])) * 0.2
		var cell := map.cell_of(pos)
		mark[cell] = ch
		# the body: 20 m along +z
		var rr := deg_to_rad(float(o["rotation"]))
		var al := Vector2(sin(rr), cos(rr))
		if ch == "w":
			for zi in range(1, 18, 4):
				var q := map.cell_of(pos + al * float(zi))
				if not mark.has(q): mark[q] = "-"
	for y in range(cy - r, cy + r + 1):
		var line := ""
		for x in range(cx - r, cx + r + 1):
			var c := Vector2i(x, y)
			var pas := map.cell_flag(c, "passable")
			var g := map.cell_flag(c, "gate")
			var m: String = mark.get(c, "")
			line += (m if m != "" else (("g" if g == 1 else ".") if pas == 1 else "#"))
		print(line)
	quit()
