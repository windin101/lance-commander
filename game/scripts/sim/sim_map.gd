class_name SimMap
extends RefCounted
## Mission terrain for the simulation: heights, the 3x3-per-vertex cell map and
## ground pathfinding. Converted by tools/convert/terrain.py.
##
## Coordinates are metres, x east, y north, origin at the map centre. The map's
## north-west corner is (-half, +half). Vertex (row, col) sits at
## (-half + col * vertex_m, half - row * vertex_m); cell rows run north to
## south, like the original (Terrain.cpp:270-277).

const CELLS_PER_VERTEX := 3
const COST_CLEAR := 100.0  # Move.h:91
const COST_BLOCKED := 10000.0
## Pass as the `hover` argument for an air mover (MOVETYPE_AIR, move level 2: the copters): it
## flies straight over anything on the map (mover.cpp:4260).
const AIR := 2

var name := ""
var meta: Dictionary = {}
var vertices_per_side := 0
var cells_per_side := 0
var vertex_m := 25.6
var cell_m := 25.6 / 3.0
var half_m := 0.0
var meters_per_wu := 0.2
var water_level_m := -1000.0
var forest_cost := 50.0  # gamesys General.ForestMoveCost
var elevation_m := PackedFloat32Array()  # per vertex, metres
var cells := PackedInt32Array()  # raw MapCell words

var _los_local := PackedFloat32Array()  # per cell: local height (objects, trees) in metres
var _los_forest := PackedByteArray()  # per cell: 1 = forest
var mines := PackedByteArray()  # per cell: 0 none, 1 laid, 2 spent (MapCell mine bits, Move.h)

var _astar: AStarGrid2D
var _astar_hover: AStarGrid2D
var _astar_offmap: Dictionary = {}  # hover -> grid with off-map cells open (movers that start off the map)
var _astar_mines: AStarGrid2D = null  # the ground grid with laid mines solid (SimUnit.avoid_mines)


static func load_mission(mission: String, base_dir: String = "res://data/maps") -> SimMap:
	var m := SimMap.new()
	m.name = mission
	var dir := base_dir.path_join(mission)
	m.meta = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("terrain.json")))
	m.vertices_per_side = int(m.meta["vertices_per_side"])
	m.cells_per_side = int(m.meta["cells_per_side"])
	m.meters_per_wu = float(m.meta["meters_per_world_unit"])
	m.vertex_m = float(m.meta["world_units_per_vertex"]) * m.meters_per_wu
	m.cell_m = m.vertex_m / CELLS_PER_VERTEX
	m.half_m = m.vertices_per_side * m.vertex_m / 2.0
	m.water_level_m = float(m.meta["water_elevation"]) * m.meters_per_wu
	for e in m.meta["elevation"]:
		m.elevation_m.append(float(e) * m.meters_per_wu)
	var raw := FileAccess.get_file_as_bytes(dir.path_join("cells.bin"))
	m.cells = raw.to_int32_array()
	assert(m.cells.size() == m.cells_per_side * m.cells_per_side, "cells.bin size mismatch")
	m._load_mines()
	return m


## The map's own mines (mc2_11's fields, mc2_15's LRM-turret valley): the cell mine state.
func _load_mines() -> void:
	mines.resize(cells.size())
	var bits: Array = meta["cell_bits"].get("mine", [13, 15])
	var shift := int(bits[0])
	var mask := int(bits[1])
	for i in cells.size():
		var v := (cells[i] >> shift) & mask
		mines[i] = 1 if v == 1 else (2 if v == 2 else 0)


func mine_at(cell: Vector2i) -> int:
	if not in_bounds(cell):
		return 0
	return mines[cell.y * cells_per_side + cell.x]


func set_mine(cell: Vector2i, state: int) -> void:
	if in_bounds(cell):
		mines[cell.y * cells_per_side + cell.x] = state
		if _astar_mines != null and is_walkable(cell, false):
			_astar_mines.set_point_solid(cell, state == 1)


# --- line of sight (Team::lineOfSight, team.cpp:1071-1260) ------------------------

const LOS_ACCURACY := 1.5  # ACCURACY_ADJUST (team.cpp:1067)


func _build_los() -> void:
	var n := cells.size()
	_los_local.resize(n)
	_los_forest.resize(n)
	var hb: Array = meta["cell_bits"]["height"]
	var fb: Array = meta["cell_bits"]["forest"]
	for i in n:
		var w := cells[i]
		# getLocalHeight x 4 x worldUnitsPerMeter world units = 4 m per step (team.cpp:1203)
		_los_local[i] = 4.0 * float((w >> int(hb[0])) & int(hb[1]))
		_los_forest[i] = (w >> int(fb[0])) & int(fb[1])


## Local (object) height of a cell in metres.
func local_height(cell: Vector2i) -> float:
	if _los_local.is_empty():
		_build_los()
	if not in_bounds(cell):
		return 0.0
	return _los_local[cell.y * cells_per_side + cell.x]


## Real line of sight from a sight point to a target point, as the original walks it:
## from the centre of the shooter's cell to the centre of the target's cell, in steps of
## 1/1.5 cell, comparing the sight line with the terrain plus each cell's local (object)
## height. A step under the terrain blocks at once; a step under a forest cell's height counts
## a tree, and max_trees trees block (MaxTreeLOSCellBlock). The walk stops early, seeing the
## target, once it is within the target's extent plus half a cell. from_h / to_h are the
## sight points' heights above the ground; start_ext_m skips the shooter's own footprint.
func line_of_sight(from: Vector2, from_h: float, to: Vector2, to_h: float, ext_m: float = 0.0,
		start_ext_m: float = 0.0, max_trees: int = 6) -> bool:
	if _los_local.is_empty():
		_build_los()
	var mc := cell_of(from)
	var tc := cell_of(to)
	var start := cell_center(mc)
	var end := cell_center(tc)
	var start_z := height_at(start) + from_h
	var end_z := height_at(end) + to_h
	var length := Vector2(tc - mc).length() * LOS_ACCURACY
	if length <= 0.0001:
		return true
	var step := (end - start) / length
	var height_step := (end_z - start_z) / (length + LOS_ACCURACY)
	var cur := start
	var line_z := start_z
	var iters := int(length - 0.5)
	var trees := 0
	var check_ext := ext_m > 0.0001
	var ext := ext_m + cell_m * 0.5  # + HALF_CELL_DIST
	var ext_sq := ext * ext
	var check_start := start_ext_m > 0.0001
	var n := cells_per_side
	for i in iters:
		line_z += height_step
		var ground := height_at(cur)
		var c := cell_of(cur)
		var idx := c.y * n + c.x
		var top := ground + (_los_local[idx] if c.x >= 0 and c.y >= 0 and c.x < n and c.y < n else 0.0)
		if check_ext:
			var dz := end_z - ground
			if (end - cur).length_squared() + dz * dz <= ext_sq:
				break
		if line_z < top and (not check_start or cur.distance_to(start) > start_ext_m):
			var tree := c.x >= 0 and c.y >= 0 and c.x < n and c.y < n and _los_forest[idx] == 1
			if tree:
				trees += 1
			if not tree or trees >= max_trees:
				return false
		cur += step
	return true


# --- coordinates ----------------------------------------------------------

func cell_of(pos: Vector2) -> Vector2i:
	return Vector2i(int(floor((pos.x + half_m) / cell_m)), int(floor((half_m - pos.y) / cell_m)))


func cell_center(cell: Vector2i) -> Vector2:
	return Vector2(-half_m + (cell.x + 0.5) * cell_m, half_m - (cell.y + 0.5) * cell_m)


func in_bounds(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < cells_per_side and cell.y < cells_per_side


func vertex_height(row: int, col: int) -> float:
	row = clampi(row, 0, vertices_per_side - 1)
	col = clampi(col, 0, vertices_per_side - 1)
	return elevation_m[row * vertices_per_side + col]


## Ground height in metres, bilinear between the four surrounding vertices.
func height_at(pos: Vector2) -> float:
	var fc := (pos.x + half_m) / vertex_m
	var fr := (half_m - pos.y) / vertex_m
	var c := int(floor(fc))
	var r := int(floor(fr))
	var tx := fc - c
	var ty := fr - r
	var top := lerpf(vertex_height(r, c), vertex_height(r, c + 1), tx)
	var bottom := lerpf(vertex_height(r + 1, c), vertex_height(r + 1, c + 1), tx)
	return lerpf(top, bottom, ty)


# --- cell flags (MapCell bits, Move.h:225-275) ----------------------------

func cell_word(cell: Vector2i) -> int:
	return cells[cell.y * cells_per_side + cell.x]


func cell_flag(cell: Vector2i, field: String) -> int:
	var bits: Array = meta["cell_bits"][field]
	return (cell_word(cell) >> int(bits[0])) & int(bits[1])


## Ground-mover cost of entering a cell (Move.cpp:4400-4470): clear 100,
## roads quarter cost, forest +ForestMoveCost; blocked when off-map, deep
## water, or not passable. Hovercraft also cross deep water. travel_offmap
## opens off-map cells, as the original does for a mover whose path starts
## off the map (Move.cpp:4379-4382, travelOffMap): reinforcements drive in.
func move_cost(cell: Vector2i, hover: bool = false, travel_offmap: bool = false) -> float:
	if not in_bounds(cell) or (cell_flag(cell, "offmap") == 1 and not travel_offmap):
		return COST_BLOCKED
	if cell_flag(cell, "deep") == 1:
		return COST_CLEAR if hover else COST_BLOCKED
	if cell_flag(cell, "passable") == 0:
		return COST_BLOCKED
	var cost := COST_CLEAR
	if cell_flag(cell, "road") == 1:
		cost /= 4.0
	if cell_flag(cell, "forest") == 1:
		cost += forest_cost
	return cost


func is_walkable(cell: Vector2i, hover = false) -> bool:
	if hover is int and hover == AIR:
		return in_bounds(cell) and cell_flag(cell, "offmap") == 0
	return move_cost(cell, bool(hover)) < COST_BLOCKED


# --- pathfinding ----------------------------------------------------------

func build_pathing() -> void:
	_astar = _build_grid(false)


func _build_grid(hover: bool, travel_offmap: bool = false) -> AStarGrid2D:
	var g := AStarGrid2D.new()
	g.region = Rect2i(0, 0, cells_per_side, cells_per_side)
	g.cell_size = Vector2(1, 1)
	g.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	g.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	g.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	g.update()
	for row in cells_per_side:
		for col in cells_per_side:
			var cell := Vector2i(col, row)
			var cost := move_cost(cell, hover, travel_offmap)
			if cost >= COST_BLOCKED:
				g.set_point_solid(cell, true)
			else:
				g.set_point_weight_scale(cell, cost / COST_CLEAR)
	return g


## Path of world positions (cell centres) from start to goal, empty if none.
## Ends exactly at the goal when the goal cell is reachable.
## avoid_mines: route round laid mines (map mine state 1), as a player steers by hand round the
## minefields everyone can see; the original's pathfinder never does (its avoidMines local is set
## but unread, MCLib/Move.cpp:4391), so this is off for every unit unless SimUnit.avoid_mines.
## Falls back to the plain path when no mine-free one exists.
func find_path(start: Vector2, goal: Vector2, hover = false, avoid_mines := false) -> PackedVector2Array:
	if hover is int and hover == AIR:
		return PackedVector2Array([goal]) if in_bounds(cell_of(goal)) else PackedVector2Array()
	hover = bool(hover)
	if _astar == null:
		build_pathing()
	if hover and _astar_hover == null:
		_astar_hover = _build_grid(true)
	var grid := _astar_hover if hover else _astar
	if avoid_mines and not hover:
		if _astar_mines == null:
			_astar_mines = _build_grid(false)
			for i in mines.size():
				if mines[i] == 1:
					var mc := Vector2i(i % cells_per_side, i / cells_per_side)
					if is_walkable(mc, false):
						_astar_mines.set_point_solid(mc, true)
		var safe := find_path(start, goal, false, false) if mine_at(cell_of(goal)) == 1 else _path_on(_astar_mines, start, goal, false)
		if not safe.is_empty():
			return safe
	return _path_on(grid, start, goal, hover)


func _path_on(grid: AStarGrid2D, start: Vector2, goal: Vector2, hover: bool) -> PackedVector2Array:
	var a := cell_of(start)
	var b := cell_of(goal)
	var out := PackedVector2Array()
	if not in_bounds(a) or not in_bounds(b) or not is_walkable(b, hover):
		return out
	if not is_walkable(a, hover) and cell_flag(a, "offmap") == 0:
		# A unit standing on a blocked cell (mc2_04's Anubis is placed inside the weapons
		# facility's footprint) walks out to the nearest open cell first; grid A* refuses a
		# solid start, which left such units frozen for the whole mission.
		var out_at := nearest_walkable(start, hover, 6)
		var c := cell_of(out_at)
		if c == a or not is_walkable(c, hover):
			return out
		out.append(cell_center(c))
		a = c
		if a == b:
			out.append(goal)
			return out
	if cell_flag(a, "offmap") == 1:  # starting off the map: off-map cells are open for this path
		if not _astar_offmap.has(hover):
			_astar_offmap[hover] = _build_grid(hover, true)
		grid = _astar_offmap[hover]
	var lead := out.size()
	for cell in grid.get_id_path(a, b):
		out.append(cell_center(cell))
	if out.size() == lead:
		return PackedVector2Array()
	out[out.size() - 1] = goal
	return out


## Nearest walkable cell centre to a position, searching outward ring by ring.
func nearest_walkable(pos: Vector2, hover = false, max_radius: int = 30) -> Vector2:
	if hover is int and hover == AIR:
		return pos
	var c := cell_of(pos)
	if in_bounds(c) and is_walkable(c, hover):
		return pos
	for radius in range(1, max_radius + 1):
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				if max(abs(dx), abs(dy)) != radius:
					continue
				var n := c + Vector2i(dx, dy)
				if in_bounds(n) and is_walkable(n, hover):
					return cell_center(n)
	return pos
