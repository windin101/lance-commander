class_name SimFixture
extends RefCounted
## Helpers for simulation tests: real converted data, deterministic RNG.


static func rules() -> SimRules:
	return SimRules.from_data(GameData)


static func mech(chassis_name: String, r: SimRules, gunnery: float = 60.0, piloting: float = 60.0, specialties: Array = []) -> SimMech:
	var m := SimMech.from_chassis(GameData.chassis[chassis_name], 0, r, SimPilot.make(gunnery, piloting, specialties))
	return m


## First inventory index holding this component master id.
static func item(m: SimMech, master_id: int) -> int:
	for i in m.items.size():
		if m.items[i]["master_id"] == master_id:
			return i
	return -1


## Two Atlases 50 m apart, facing each other: attacker at the origin facing north.
static func duel(r: SimRules, distance: float = 50.0) -> Array:
	var a := mech("atlas", r)
	a.is_player = true
	var t := mech("atlas", r)
	t.position = Vector2(0, distance)
	t.facing = 180.0
	return [a, t]


const BITS := {"terrain": [0, 15], "overlay": [4, 3], "gate": [8, 1], "offmap": [9, 1], "passable": [10, 1],
	"mine": [13, 15], "height": [18, 15], "wall": [24, 1], "road": [25, 1], "shallow": [26, 1], "deep": [27, 1],
	"forest": [28, 1]}


## A flat, open map of vps x vps vertices (25.6 m each), centred on the origin.
static func flat_map(vps := 60) -> SimMap:
	var m := SimMap.new()
	m.meta = {"cell_bits": BITS}
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


## Forest cells with a local height (4 m steps) on the column of cells under x = at_x, rows
## covering y in [y0, y1).
static func forest_strip(m: SimMap, at_x: float, y0: float, y1: float, height_steps := 5) -> int:
	var n := 0
	var y := y0
	while y < y1:
		var c := m.cell_of(Vector2(at_x, y))
		m.cells[c.y * m.cells_per_side + c.x] = (1 << 10) | (1 << 28) | (height_steps << 18)
		n += 1
		y += m.cell_m
	return n
