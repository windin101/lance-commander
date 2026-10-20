class_name PaperDoll
extends RefCounted
## Damage diagram helpers: per-location colour from armour and internal
## structure, and layouts (unit square, origin top-left) for mechs and vehicles.
## Per-unit index masks (assets/ui/dolls/<model>_doll.png: R = location index in
## SimMech.Body / SimVehicle.Section order, 255 empty) replace the rectangles when
## present; mask_for() loads and crops them, DollView draws either.

const OK := Color(0.310, 0.827, 0.541)  # the HUD's ok green
const SCRATCHED := Color(0.78, 0.85, 0.32)
const HOLED := Color(0.949, 0.710, 0.290)  # HUD warn
const CRITICAL := Color(1.0, 0.353, 0.306)  # HUD crit
const GONE := Color(0.22, 0.24, 0.26)
const DOLL_DIR := "res://assets/ui/dolls"
const TORSO_REAR := {SimMech.Body.CTORSO: SimMech.Armor.RCTORSO, SimMech.Body.LTORSO: SimMech.Armor.RLTORSO,
	SimMech.Body.RTORSO: SimMech.Armor.RRTORSO}

static var _masks := {}  # model -> {"texture": ImageTexture, "region": Rect2 (px)} or {}

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


## Colour per location for the doll (8 for a mech, 5 for a vehicle). Front uses the front
## armour; rear lights only the three torso locations, from their rear armour (the original's
## rear damage diagram), and leaves the rest as a faint silhouette.
static func location_colours(u: SimUnit, rear := false) -> PackedColorArray:
	var out := PackedColorArray()
	out.resize(8)
	out.fill(Color(0, 0, 0, 0))
	if u is SimMech:
		for loc in 8:
			if rear and not TORSO_REAR.has(loc):
				out[loc] = Color(0.56, 0.65, 0.70, 0.3)
				continue
			var a: int = TORSO_REAR[loc] if rear else loc
			out[loc] = color(u.armor[a], u.max_armor[a], u.internal[loc], u.max_internal[loc])
	elif u is SimVehicle:
		for s in 5:
			out[s] = color(u.armor[s], u.max_armor[s], u.internal[s], u.max_internal[s])
	return out


## The index mask for a unit model, cropped to its used pixels, or {} when there is none
## (DollView then falls back to the rectangle layouts). Loaded once per model.
static func mask_for(model: String) -> Dictionary:
	if _masks.has(model):
		return _masks[model]
	var out := {}
	var path := "%s/%s_doll.png" % [DOLL_DIR, model]
	var img: Image = null
	if FileAccess.file_exists(path):
		img = Image.new()
		if img.load_png_from_buffer(FileAccess.get_file_as_bytes(path)) != 0:  # Error.OK (OK here is the colour)
			img = null
	if img == null and ResourceLoader.exists(path):
		var tex = load(path)
		if tex is Texture2D:
			img = (tex as Texture2D).get_image()
	if img != null and not img.is_empty():
		if img.is_compressed():
			img.decompress()
		img.convert(Image.FORMAT_R8)
		var data := img.get_data()
		var w := img.get_width()
		var h := img.get_height()
		var lo := Vector2i(w, h)
		var hi := Vector2i(-1, -1)
		for y in h:
			var row := y * w
			for x in w:
				if data[row + x] != 255:
					lo = Vector2i(mini(lo.x, x), mini(lo.y, y))
					hi = Vector2i(maxi(hi.x, x), maxi(hi.y, y))
		if hi.x >= 0:
			var pad := 2
			lo = (lo - Vector2i(pad, pad)).max(Vector2i.ZERO)
			hi = (hi + Vector2i(pad, pad)).min(Vector2i(w - 1, h - 1))
			out = {"texture": ImageTexture.create_from_image(img), "region": Rect2(Vector2(lo), Vector2(hi - lo + Vector2i.ONE))}
	_masks[model] = out
	return out
