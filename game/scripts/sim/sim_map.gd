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

var _astar: AStarGrid2D
var _astar_hover: AStarGrid2D
var _astar_offmap: Dictionary = {}  # hover -> grid with off-map cells open (movers that start off the map)


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
	return m


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


func is_walkable(cell: Vector2i, hover: bool = false) -> bool:
	return move_cost(cell, hover) < COST_BLOCKED


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
func find_path(start: Vector2, goal: Vector2, hover: bool = false) -> PackedVector2Array:
	if _astar == null:
		build_pathing()
	if hover and _astar_hover == null:
		_astar_hover = _build_grid(true)
	var grid := _astar_hover if hover else _astar
	var a := cell_of(start)
	var b := cell_of(goal)
	var out := PackedVector2Array()
	if not in_bounds(a) or not in_bounds(b) or not is_walkable(b, hover):
		return out
	if cell_flag(a, "offmap") == 1:  # starting off the map: off-map cells are open for this path
		if not _astar_offmap.has(hover):
			_astar_offmap[hover] = _build_grid(hover, true)
		grid = _astar_offmap[hover]
	for cell in grid.get_id_path(a, b):
		out.append(cell_center(cell))
	if out.size() > 0:
		out[out.size() - 1] = goal
	return out


## Nearest walkable cell centre to a position, searching outward ring by ring.
func nearest_walkable(pos: Vector2, hover: bool = false, max_radius: int = 30) -> Vector2:
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
