class_name PaperDoll
extends RefCounted
## Damage diagram helpers: per-location colour from armour and internal
## structure, and layouts (unit square, origin top-left) for mechs and vehicles.

const OK := Color(0.30, 0.85, 0.35)
const SCRATCHED := Color(0.85, 0.85, 0.25)
const HOLED := Color(0.95, 0.55, 0.15)
const CRITICAL := Color(0.90, 0.15, 0.12)
const GONE := Color(0.15, 0.15, 0.15)

# Mech body locations (SimMech.Body order) -> rect in a 1x1 box.
const MECH_LAYOUT := [
	Rect2(0.40, 0.00, 0.20, 0.13),  # head
	Rect2(0.38, 0.15, 0.24, 0.33),  # ctorso
	Rect2(0.20, 0.17, 0.17, 0.28),  # ltorso
	Rect2(0.63, 0.17, 0.17, 0.28),  # rtorso
	Rect2(0.03, 0.17, 0.15, 0.38),  # larm
	Rect2(0.82, 0.17, 0.15, 0.38),  # rarm
	Rect2(0.27, 0.50, 0.20, 0.50),  # lleg
	Rect2(0.53, 0.50, 0.20, 0.50),  # rleg
]
# Vehicle sections (SimVehicle.Section order).
const VEHICLE_LAYOUT := [
	Rect2(0.25, 0.00, 0.50, 0.22),  # front
	Rect2(0.00, 0.24, 0.22, 0.52),  # left
	Rect2(0.78, 0.24, 0.22, 0.52),  # right
	Rect2(0.25, 0.78, 0.50, 0.22),  # rear
	Rect2(0.32, 0.32, 0.36, 0.36),  # turret
]


## Colour for one location: green while armour holds, through yellow/orange as
## it wears, red once internal structure is damaged, dark when destroyed.
static func color(armor: float, max_armor: float, internal: float, max_internal: float) -> Color:
	if max_internal > 0.0 and internal <= 0.0:
		return GONE
	if max_internal > 0.0 and internal < max_internal:
		return CRITICAL
	var a := armor / max_armor if max_armor > 0.0 else 1.0
	if a > 0.66:
		return OK
	if a > 0.33:
		return SCRATCHED
	return HOLED


## [rect, colour] pairs for a unit, in a box of the given size at origin.
static func cells(u: SimUnit, box: Rect2) -> Array:
	var out := []
	if u is SimMech:
		for loc in MECH_LAYOUT.size():
			var armor: float = u.armor[loc]
			var max_a: float = u.max_armor[loc]
			if loc in [SimMech.Body.CTORSO, SimMech.Body.LTORSO, SimMech.Body.RTORSO]:
				var rear: int = [0, SimMech.Armor.RCTORSO, SimMech.Armor.RLTORSO, SimMech.Armor.RRTORSO][loc]
				armor += u.armor[rear]
				max_a += u.max_armor[rear]
			out.append([_place(MECH_LAYOUT[loc], box), color(armor, max_a, u.internal[loc], u.max_internal[loc])])
	elif u is SimVehicle:
		for s in VEHICLE_LAYOUT.size():
			out.append([_place(VEHICLE_LAYOUT[s], box), color(u.armor[s], u.max_armor[s], u.internal[s], u.max_internal[s])])
	return out


static func _place(r: Rect2, box: Rect2) -> Rect2:
	return Rect2(box.position + r.position * box.size, r.size * box.size)


## Overall armour fraction (for compact bars).
static func armor_fraction(u: SimUnit) -> float:
	var a := 0.0
	var m := 0.0
	for i in u.armor.size():
		a += u.armor[i]
		m += u.max_armor[i]
	return a / m if m > 0.0 else 0.0
