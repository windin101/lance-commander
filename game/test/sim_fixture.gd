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
