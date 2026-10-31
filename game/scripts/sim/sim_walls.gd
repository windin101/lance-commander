class_name SimWalls
extends RefCounted
## Walls and gates (LANCE-21): footprints stamped into the move map at mission load, gates by team. See SimMap (walls and gates section).
## Walls: the placed pieces are SimStructures already (class 1, DmgLevel 30-90); this stamps the cells they cover and opens them when destroyed.
## Gates (class 22, objects.json damage_level 0 because the converter skips GateData): built as SimStructures with the FIT's DmgLevel and
## OpenRadius (Data/Objects/*Gate.fit), neutral to targeting (team -1) but owning a gate_team, which follows the control building's team.

## appearance suffix -> [post z0, post z1, post width, body half width, body z end]
const WALLS := {
	"lightwall": [-10.6, -6.5, 4.0, 1.5, 17.1], "mediumwall": [-11.5, -5.5, 6.0, 2.0, 17.1], "heavywall": [-11.5, -5.5, 6.0, 2.0, 17.1],
}
const POSTS := {"lightpost": [-10.6, -6.5, 4.0], "mediumpost": [-11.5, -5.5, 6.0], "heavypost": [-11.5, -5.5, 6.0]}
## gate suffix -> [DmgLevel, OpenRadius m, side half width, door half gap]
const GATES := {"lightgate": [25.0, 40.0, 2.0, 6.9], "mediumgate": [35.0, 40.0, 3.0, 6.9], "heavygate": [75.0, 60.0, 3.0, 6.9]}
const GATE_END := 27.7
const STEP := 1.5


static func suffix(appearance: String) -> String:
	return appearance.substr(2) if appearance.length() > 2 and appearance[1] == "_" else appearance


static func is_wall(appearance: String) -> bool:
	var s := suffix(appearance)
	return WALLS.has(s) or POSTS.has(s)


static func is_gate(appearance: String) -> bool:
	return GATES.has(suffix(appearance))


## Cells a placed wall piece covers (rotation in degrees as objects.json gives it; local +z runs (sin r, cos r) on the sim plane).
static func wall_cells(map: SimMap, appearance: String, pos: Vector2, rotation_deg: float) -> Array[Vector2i]:
	var r := deg_to_rad(rotation_deg)
	var along := Vector2(sin(r), cos(r))
	var across := Vector2(-cos(r), sin(r))
	var out: Array[Vector2i] = []
	var seen := {}
	var rects: Array = []  # [z0, z1, half width]
	var s := suffix(appearance)
	if WALLS.has(s):
		var w: Array = WALLS[s]
		rects = [[w[0], w[1], w[2] / 2.0], [w[1], w[4], w[3]]]
	elif POSTS.has(s):
		var w: Array = POSTS[s]
		rects = [[w[0], w[1], w[2] / 2.0]]
	for rc in rects:
		var z := float(rc[0])
		while z <= float(rc[1]) + 0.001:
			var x := -float(rc[2])
			while x <= float(rc[2]) + 0.001:
				var c := map.cell_of(pos + along * z + across * x)
				if not seen.has(c):
					seen[c] = true
					out.append(c)
				x += STEP
			z += STEP
	return out


## A gate's side pieces (blocked for good) and its door cells (gated by team).
static func gate_parts(map: SimMap, appearance: String, pos: Vector2, rotation_deg: float) -> Dictionary:
	var g: Array = GATES[suffix(appearance)]
	var r := deg_to_rad(rotation_deg)
	var along := Vector2(sin(r), cos(r))
	var across := Vector2(-cos(r), sin(r))
	var sides: Array[Vector2i] = []
	var door: Array[Vector2i] = []
	var seen := {}
	var gap := float(g[3])
	var z := -GATE_END
	while z <= GATE_END + 0.001:
		var in_door := absf(z) <= gap - 1.5
		var edge := absf(z) > gap - 1.5 and absf(z) < gap + 1.5  # the posts of the opening: no stamp, so the door cells stay passable
		var x := -float(g[2])
		while x <= float(g[2]) + 0.001:
			var c := map.cell_of(pos + along * z + across * x)
			if in_door or edge:
				if in_door and not seen.has(c):
					seen[c] = true
					door.append(c)
			elif not seen.has(c):
				seen[c] = true
				sides.append(c)
			x += STEP
		z += STEP
	# a cell shared by a door sample and a side sample stays a side (blocked): the opening is at least the door cells nobody else claims
	var door_only: Array[Vector2i] = []
	for c in door:
		if not sides.has(c):
			door_only.append(c)
	return {"sides": sides, "door": door_only}


## The original's special-area footprints for a mission (maps/<m>/special_areas.json, converter: terrain.read_special_areas):
## {object cell: [area, ...]} where an area is the Array of cells it covers; (row, col) in the file are (y, x) here.
static func load_areas(mission: String) -> Dictionary:
	var path := "res://data/maps/%s/special_areas.json" % mission
	var out := {}
	if not FileAccess.file_exists(path):
		return out
	for a in JSON.parse_string(FileAccess.get_file_as_string(path)):
		var key := Vector2i(int(a[1]), int(a[0]))
		var cs: Array[Vector2i] = []
		for rc in a[2]:
			cs.append(Vector2i(int(rc[1]), int(rc[0])))
		if not out.has(key):
			out[key] = []
		out[key].append(cs)
	return out


## The next unused footprint of the object standing in `cell` (objmgr.cpp:1215-1226 matches by the object's cell), or [].
static func take_area(areas: Dictionary, cell: Vector2i) -> Array[Vector2i]:
	var list: Array = areas.get(cell, [])
	if list.is_empty():
		return []
	return list.pop_front()


static func update_gates(world: SimWorld) -> void:
	for gs in world.gates:
		var map := world.map
		var parent: SimStructure = gs.parent
		var locked := gs.is_destroyed() or (parent != null and (parent.is_destroyed() or parent.is_disabled()))
		var team := gs.gate_team
		if parent != null:
			team = parent.team if parent.team >= 0 else gs.gate_team
		var g: Dictionary = map.gates[gs.gate_id]
		if gs.is_destroyed():
			continue
		if int(g["team"]) != team or bool(g["locked"]) != locked:
			map.set_gate(gs.gate_id, team, locked, false)
		var want := false
		if not locked:
			for m in world.movers():
				if m.flying or m.is_disabled() or not m.exists:
					continue
				if (team == -1 or m.team == team) and m.position.distance_to(gs.position) <= gs.gate_open_radius_m:
					want = true
					break
		if want != gs.gate_open:
			gs.gate_open = want
			world.events.append({"type": "gate_state", "index": gs.object_index, "open": want})


static func structure_down(world: SimWorld, s: SimStructure) -> void:
	if not s.wall_cells.is_empty():
		world.map.open_cells(s.wall_cells)
		s.wall_cells = []
	if s.gate_id >= 0:
		world.map.set_gate(s.gate_id, -1, false, true)
		if not s.gate_open:
			s.gate_open = true
			world.events.append({"type": "gate_state", "index": s.object_index, "open": true})
