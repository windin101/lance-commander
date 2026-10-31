extends SceneTree
# Footprint coverage per mission: the original's special areas vs our raster. godot --headless --path game -s res://tools/wall_cover.gd
func _init() -> void:
	var data = load("res://scripts/data/game_data.gd").new()
	data.load_all()
	for n in range(1, 25):
		var m := "mc2_%02d" % n
		var w := SimMission.load_mission(data, m, 1, false)
		var st: Dictionary = w.world.map.stamp_stats
		var a: Dictionary = st["area_cells"]
		var r: Dictionary = st["raster_cells"]
		var both := 0
		for c in a:
			if r.has(c):
				both += 1
		print("%s area_pieces=%d raster_pieces=%d area_cells=%d raster_cells=%d both=%d" % [m, st["area_pieces"], st["raster_pieces"], a.size(), r.size(), both])
	quit()
