extends GdUnitTestSuite
## Every campaign mission is converted and loads in the sim: no skipped parts, every
## mover has an ABL part ID and brain, the scripts load without errors.


func test_every_campaign_mission_loads() -> void:
	var problems: Array[String] = []
	for i in range(1, 25):
		var m := "mc2_%02d" % i
		if not FileAccess.file_exists("res://data/missions/%s.json" % m):
			problems.append("%s: not converted" % m)
			continue
		var sm := SimMission.load_mission(GameData, m, 1)
		var movers := sm.world.units.filter(func(u): return u.is_mover())
		if not sm.skipped.is_empty():
			problems.append("%s: skipped %s" % [m, sm.skipped])
		if movers.any(func(u): return u.part_id == 0):
			problems.append("%s: movers without part id" % m)
		if sm.abl == null or sm.abl.pilots.size() != movers.size():
			problems.append("%s: brains %d of %d" % [m, sm.abl.pilots.size() if sm.abl else 0, movers.size()])
		elif not sm.abl.runtime.errors.is_empty():
			problems.append("%s: abl %s" % [m, sm.abl.runtime.errors.slice(0, 2)])
	assert_array(problems).is_empty()
