class_name Loadout
extends RefCounted
## Mech Lab fitting rules (issue I86, MechWarrior 5-style; approved 2026-10-21). Pure and
## UI-free: every function takes the game data (GameData: .chassis, .components) and plain
## dictionaries.
##
## A loadout's "parts" are the removable components per body location, {loc: [component
## id, ...]} over LOCS. Fixed items (engine, gyro, actuators, cockpit, life support,
## sensors) are not parts: they stay where the mech's base variant puts them. Ammo is
## implicit: each fitted weapon that uses ammo gets one bin of its ammo master.
##
## Rules:
##  1. Hardpoints: per location, the most weapons of each type (B ballistic, E energy, M
##     missile) any non-hidden stock variant of the chassis carries there. A weapon needs a
##     free hardpoint of its type; equipment needs none. A component's `locations` map
##     says where it may go at all (-1: never).
##  2. Tonnage: structure = tonnage - the heaviest stock payload (component tons, ammo
##     excluded); structure + parts must be <= tonnage.
##  3. Slots: capacity = max(standard 6 head/legs, 12 elsewhere; the most any stock variant
##     uses there counting fixed items). Ammo takes no slot.
##  4. Heat: alpha heat over capacity (heat_index + 4 per heat sink) warns but is allowed.
##  5. Armour: plating (id 25) adds 32 armour up to max_armor; armour = base + 32 x plates.
##  6. Jump jets: legs only, and only on a chassis that allows them. A chassis allows them
##     when `allow.jump_jets` is set or one of its stock variants carries them (twelve stock
##     designs mount jets on a chassis whose flag is off; they must stay legal).

const LOCS := ["head", "ctorso", "ltorso", "rtorso", "larm", "rarm", "lleg", "rleg"]
const LOC_NAMES := {"head": "Head", "ctorso": "Centre torso", "ltorso": "Left torso", "rtorso": "Right torso",
	"larm": "Left arm", "rarm": "Right arm", "lleg": "Left leg", "rleg": "Right leg"}
const LOC_SHORT := {"head": "HD", "ctorso": "CT", "ltorso": "LT", "rtorso": "RT", "larm": "LA", "rarm": "RA",
	"lleg": "LL", "rleg": "RL"}
const STD_SLOTS := {"head": 6, "ctorso": 12, "ltorso": 12, "rtorso": 12, "larm": 12, "rarm": 12, "lleg": 6, "rleg": 6}
const FIXED_FORMS := ["Engine", "Gyroscope", "Actuator", "Cockpit", "LifeSupport", "Sensors"]
const TYPE_OF := {"BallisticWeapon": "B", "EnergyWeapon": "E", "MissileWeapon": "M"}
const TYPE_NAMES := {"B": "ballistic", "E": "energy", "M": "missile", "X": "equipment"}
const ARMOR_PLATE := 25
const PLATE_ARMOR := 32
const HEAT_PER_SINK := 4.0
const RANGE_RANK := {"short": 1, "medium": 2, "long": 3}
const RANGE_NAMES := ["–", "Short", "Medium", "Long"]
## Chassis speed -> displayed km/h (campaign-layer.md 4.3, LogisticsVariant.cpp:130-160).
const SPEED_TABLE := [[5, 17], [10, 34], [15, 54], [19, 65], [23, 86], [27, 97], [31, 119], [35, 130]]
const EPS := 0.0001

static var _info_cache := {}


# --- components ---------------------------------------------------------------------------

static func component(data: Object, id: int) -> Dictionary:
	return data.components.get(id, {})


static func is_fixed(comp: Dictionary) -> bool:
	return String(comp.get("form", "")) in FIXED_FORMS


static func is_ammo(comp: Dictionary) -> bool:
	return String(comp.get("form", "")) == "Ammo"


static func is_weapon(comp: Dictionary) -> bool:
	return TYPE_OF.has(String(comp.get("form", "")))


## A part a player can fit: a weapon or equipment, never a fixed item or ammo.
static func is_part(comp: Dictionary) -> bool:
	return not comp.is_empty() and not is_fixed(comp) and not is_ammo(comp)


## "B", "E", "M" for weapons, "X" for equipment.
static func kind(comp: Dictionary) -> String:
	return TYPE_OF.get(String(comp.get("form", "")), "X")


static func allowed_in(comp: Dictionary, loc: String) -> bool:
	return int(comp.get("locations", {}).get(loc, -1)) >= 0


static func kmh(speed: float) -> int:
	for row in SPEED_TABLE:
		if speed <= row[0]:
			return row[1]
	return 130


# --- chassis --------------------------------------------------------------------------------

## Non-hidden variants (all of them if every one is hidden).
static func stock_variants(ch: Dictionary) -> Array:
	var vs: Array = ch.get("variants", [])
	var out := vs.filter(func(v): return not v.get("hidden", false))
	return out if not out.is_empty() else vs


## A chassis the Mech Lab can refit: a 'Mech with an armour maximum ('Copters and the
## scripted Talon chassis have none).
static func lab_allowed(data: Object, chassis: String) -> bool:
	var ch: Dictionary = data.chassis.get(chassis, {})
	return not ch.is_empty() and float(ch.get("max_armor", 0)) > 0.0


## The distinct, non-ammo items a variant places in a location: [[item index, id], ...].
static func _placed(data: Object, v: Dictionary, loc: String, with_ammo := false) -> Array:
	var items: Array = v.get("items", [])
	var seen := {}
	var out := []
	for s in v.get("crit_slots", {}).get(loc, []):
		if s == null or seen.has(int(s)) or int(s) >= items.size() or items[int(s)] == null:
			continue
		seen[int(s)] = true
		var id := int(items[int(s)])
		if not with_ammo and is_ammo(component(data, id)):
			continue
		out.append([int(s), id])
	return out


## Derived per-chassis numbers (cached): tonnage, structure, hardpoints {loc: {B,E,M}},
## slot capacity {loc}, jump jets allowed, base/max armour, heat index, speed.
static func info(data: Object, chassis: String) -> Dictionary:
	if _info_cache.has(chassis):
		return _info_cache[chassis]
	var ch: Dictionary = data.chassis.get(chassis, {})
	var hp := {}
	var cap := {}
	for loc in LOCS:
		hp[loc] = {"B": 0, "E": 0, "M": 0}
		cap[loc] = int(STD_SLOTS[loc])
	var payload := 0.0
	var stock_jets := false
	for v in stock_variants(ch):
		var tons := 0.0
		for loc in LOCS:
			var count := {"B": 0, "E": 0, "M": 0}
			var used := 0
			for p in _placed(data, v, loc):
				var c := component(data, p[1])
				used += int(c.get("crits", 0))
				tons += float(c.get("tons", 0.0))
				if is_weapon(c):
					count[kind(c)] += 1
				if String(c.get("form", "")) == "JumpJet":
					stock_jets = true
			for t in count:
				hp[loc][t] = maxi(hp[loc][t], count[t])
			cap[loc] = maxi(cap[loc], used)
		payload = maxf(payload, tons)
	var base_armor := 0.0
	for k in ch.get("base_armor", {}):
		base_armor += float(ch["base_armor"][k])
	var tonnage := float(ch.get("tonnage", 0))
	var out := {
		"tonnage": tonnage, "structure": tonnage - payload, "hardpoints": hp, "slots": cap,
		"jump_jets": bool(ch.get("allow", {}).get("jump_jets", false)) or stock_jets,
		"base_armor": base_armor, "max_armor": float(ch.get("max_armor", 0)),
		"heat_index": float(ch.get("heat_index", 0)), "speed": float(ch.get("max_run_speed", 0)),
		"name": String(ch.get("name", chassis)),
	}
	_info_cache[chassis] = out
	return out


static func variant(data: Object, chassis: String, index: int) -> Dictionary:
	var vs: Array = data.chassis.get(chassis, {}).get("variants", [])
	return vs[index] if index >= 0 and index < vs.size() else {}


## Fixed items' crits per location in a variant.
static func fixed_slots(data: Object, chassis: String, index: int) -> Dictionary:
	var v := variant(data, chassis, index)
	var out := {}
	for loc in LOCS:
		var n := 0
		for p in _placed(data, v, loc):
			var c := component(data, p[1])
			if is_fixed(c):
				n += int(c.get("crits", 0))
		out[loc] = n
	return out


## A variant's parts, in crit-slot order.
static func stock_parts(data: Object, chassis: String, index: int) -> Dictionary:
	var v := variant(data, chassis, index)
	var out := {}
	for loc in LOCS:
		var list: Array = []
		for p in _placed(data, v, loc):
			if is_part(component(data, p[1])):
				list.append(p[1])
		out[loc] = list
	return out


## Parts with int ids and every location present (JSON round-trips give floats).
static func normalize(parts: Dictionary) -> Dictionary:
	var out := {}
	for loc in LOCS:
		var list: Array = []
		for id in parts.get(loc, []):
			list.append(int(id))
		out[loc] = list
	return out


static func copy(parts: Dictionary) -> Dictionary:
	return normalize(parts)


## Same parts in each location, order ignored.
static func same(a: Dictionary, b: Dictionary) -> bool:
	for loc in LOCS:
		var x: Array = a.get(loc, []).map(func(i): return int(i))
		var y: Array = b.get(loc, []).map(func(i): return int(i))
		x.sort()
		y.sort()
		if x != y:
			return false
	return true


## {id: count} over every location.
static func counts(parts: Dictionary) -> Dictionary:
	var out := {}
	for loc in LOCS:
		for id in parts.get(loc, []):
			out[int(id)] = int(out.get(int(id), 0)) + 1
	return out


# --- usage ---------------------------------------------------------------------------------

static func tons(data: Object, chassis: String, parts: Dictionary) -> float:
	var t := float(info(data, chassis)["structure"])
	for loc in LOCS:
		for id in parts.get(loc, []):
			t += float(component(data, int(id)).get("tons", 0.0))
	return t


static func slots_used(data: Object, chassis: String, index: int, parts: Dictionary, loc: String) -> int:
	var n := int(fixed_slots(data, chassis, index)[loc])
	for id in parts.get(loc, []):
		n += int(component(data, int(id)).get("crits", 0))
	return n


static func hardpoints_used(data: Object, parts: Dictionary, loc: String, type: String) -> int:
	var n := 0
	for id in parts.get(loc, []):
		var c := component(data, int(id))
		if is_weapon(c) and kind(c) == type:
			n += 1
	return n


static func plates(parts: Dictionary) -> int:
	return int(counts(parts).get(ARMOR_PLATE, 0))


static func short_name(name: String) -> String:
	match name:
		"Light Autocannon (AC5)": return "AC/5"
		"Autocannon (AC10)": return "AC/10"
		"Heavy Autocannon (AC20)": return "AC/20"
		"Light Ultra Autocannon (AC5)": return "Ultra AC/5"
		"Ultra Autocannon (AC10)": return "Ultra AC/10"
		"Heavy Ultra Autocannon (AC20)": return "Ultra AC/20"
		"Clan Light Ultra Autocannon (AC5)": return "Clan Ultra AC/5"
		"Clan Ultra Autocannon (AC10)": return "Clan Ultra AC/10"
		"Clan Heavy Ultra Autocannon (AC20)": return "Clan Ultra AC/20"
	return name.replace(" Rack", "").replace(" Pack", "").replace(" Array", "")


# --- the rules -----------------------------------------------------------------------------

## Why `id` can't be fitted to `loc` of this loadout, or "" when it can (rules 1-3, 5, 6).
static func fits(data: Object, chassis: String, index: int, parts: Dictionary, id: int, loc: String) -> String:
	var c := component(data, id)
	var nm := short_name(String(c.get("name", "?")))
	if not is_part(c):
		return "%s can't be fitted in the Mech Lab." % nm
	var inf := info(data, chassis)
	var where := String(LOC_NAMES[loc]).to_lower()
	if String(c.get("form", "")) == "JumpJet" and not inf["jump_jets"]:
		return "The %s can't mount jump jets." % inf["name"]
	if not allowed_in(c, loc):
		return "%s can't go in the %s." % [nm, where]
	if is_weapon(c):
		var t := kind(c)
		if hardpoints_used(data, parts, loc, t) >= int(inf["hardpoints"][loc][t]):
			return "The %s has no free %s hardpoint." % [where, TYPE_NAMES[t]]
	var cap := int(inf["slots"][loc])
	var used := slots_used(data, chassis, index, parts, loc)
	if used + int(c.get("crits", 0)) > cap:
		return "Not enough slots: %s needs %d, the %s has %d free." % [nm, int(c.get("crits", 0)), where, cap - used]
	var now := tons(data, chassis, parts)
	if now + float(c.get("tons", 0.0)) > float(inf["tonnage"]) + EPS:
		return "Too heavy: %s needs %.1f t, %.1f t free." % [nm, float(c.get("tons", 0.0)), float(inf["tonnage"]) - now]
	if id == ARMOR_PLATE and inf["base_armor"] + PLATE_ARMOR * (plates(parts) + 1) > inf["max_armor"] + EPS:
		return "Armour is at the chassis maximum."
	return ""


## Every rule a whole loadout breaks ([] when legal).
static func problems(data: Object, chassis: String, index: int, parts: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var inf := info(data, chassis)
	for loc in LOCS:
		var where := String(LOC_NAMES[loc]).to_lower()
		for id in parts.get(loc, []):
			var c := component(data, int(id))
			if not is_part(c):
				out.append("%s: component %d is not a part" % [where, int(id)])
			elif not allowed_in(c, loc):
				out.append("%s: %s not allowed there" % [where, c["name"]])
			elif String(c.get("form", "")) == "JumpJet" and not inf["jump_jets"]:
				out.append("%s: jump jets not allowed on this chassis" % where)
		for t in ["B", "E", "M"]:
			var n := hardpoints_used(data, parts, loc, t)
			if n > int(inf["hardpoints"][loc][t]):
				out.append("%s: %d %s weapons, %d hardpoints" % [where, n, TYPE_NAMES[t], int(inf["hardpoints"][loc][t])])
		var used := slots_used(data, chassis, index, parts, loc)
		if used > int(inf["slots"][loc]):
			out.append("%s: %d slots used of %d" % [where, used, int(inf["slots"][loc])])
	var total := tons(data, chassis, parts)
	if total > float(inf["tonnage"]) + EPS:
		out.append("%.1f t over a %d t chassis" % [total, int(inf["tonnage"])])
	var armour := float(inf["base_armor"]) + PLATE_ARMOR * plates(parts)
	if armour > float(inf["max_armor"]) + EPS:
		out.append("armour %d over the maximum %d" % [int(armour), int(inf["max_armor"])])
	return out


## Lab and bay figures: tons, alpha (damage), dps, heat (alpha heat), heat_cap, armor,
## max_armor, speed (km/h), range (0-3), jump, weapons, sinks, plates.
static func stats(data: Object, chassis: String, parts: Dictionary) -> Dictionary:
	var inf := info(data, chassis)
	var alpha := 0.0
	var dps := 0.0
	var heat := 0.0
	var sink := 0.0
	var rng := 0
	var weapons := 0
	var jump := false
	var n_plates := 0
	for loc in LOCS:
		for id in parts.get(loc, []):
			var c := component(data, int(id))
			var w: Dictionary = c.get("weapon", {})
			if is_weapon(c):
				weapons += 1
				alpha += float(w.get("damage", 0.0))
				dps += float(w.get("damage", 0.0)) / maxf(0.01, float(w.get("recycle", 1.0)))
				heat += float(w.get("heat", 0.0))
				rng = maxi(rng, int(RANGE_RANK.get(String(w.get("range", "")), 0)))
			match String(c.get("form", "")):
				"HeatSink": sink += float(c.get("heatsink", {}).get("dissipation", HEAT_PER_SINK))
				"JumpJet": jump = true
			if int(id) == ARMOR_PLATE:
				n_plates += 1
	return {"tons": tons(data, chassis, parts), "tonnage": inf["tonnage"], "alpha": alpha, "dps": dps, "heat": heat,
		"heat_cap": float(inf["heat_index"]) + sink, "armor": float(inf["base_armor"]) + PLATE_ARMOR * n_plates,
		"max_armor": inf["max_armor"], "speed": kmh(inf["speed"]), "range": rng, "jump": jump, "weapons": weapons,
		"plates": n_plates}


## A mech's value: chassis price + its base variant's fixed items + its parts (C-Bills).
static func value(data: Object, chassis: String, index: int, parts: Dictionary) -> int:
	var total := int(data.chassis.get(chassis, {}).get("cbills", 0))
	var v := variant(data, chassis, index)
	for loc in LOCS:
		for p in _placed(data, v, loc):
			var c := component(data, p[1])
			if is_fixed(c):
				total += int(c.get("rp", 0))
	for loc in LOCS:
		for id in parts.get(loc, []):
			total += int(component(data, int(id)).get("rp", 0))
	return total


## The bill for changing old_parts to new_parts: parts that leave go to stores, parts that
## arrive come from stores first (free), the rest are bought at their rp from the market
## (market: {id: true} or {"all": true}). Moving a part between locations costs nothing.
## Returns {cost, bought {id: n}, from_stores {id: n}, to_stores {id: n}, stores (after),
## unavailable [ids that would have to be bought but aren't for sale]}.
static func quote(data: Object, old_parts: Dictionary, new_parts: Dictionary, stores: Dictionary, market: Dictionary) -> Dictionary:
	var before := counts(old_parts)
	var after := counts(new_parts)
	var ids := {}
	for id in before:
		ids[id] = true
	for id in after:
		ids[id] = true
	for id in stores:
		ids[int(id)] = true
	var out := {"cost": 0, "bought": {}, "from_stores": {}, "to_stores": {}, "stores": {}, "unavailable": []}
	for id in ids:
		var have := int(stores.get(id, 0))
		var delta := int(after.get(id, 0)) - int(before.get(id, 0))
		if delta < 0:
			out["to_stores"][id] = -delta
			have += -delta
		elif delta > 0:
			var free := mini(delta, have)
			if free > 0:
				out["from_stores"][id] = free
				have -= free
			var buy := delta - free
			if buy > 0:
				out["bought"][id] = buy
				out["cost"] += buy * int(component(data, id).get("rp", 0))
				if not (market.has("all") or market.has(id)):
					out["unavailable"].append(id)
		if have > 0:
			out["stores"][id] = have
	return out


# --- the sim's view --------------------------------------------------------------------------

## {name, parts, items, crit_slots, armor_plates} for SimMech.from_chassis: the base
## variant's own item list when the parts are its stock parts, otherwise the variant's
## fixed items where they were, each part in its location, and one ammo bin per ammo
## weapon next to it.
static func to_sim(data: Object, chassis: String, index: int, parts: Dictionary, name := "") -> Dictionary:
	var v := variant(data, chassis, index)
	var p := normalize(parts)
	if name.is_empty():
		name = String(v.get("name", chassis))
	if same(p, stock_parts(data, chassis, index)):
		return {"name": name, "parts": p, "items": v.get("items", []).duplicate(true),
			"crit_slots": v.get("crit_slots", {}).duplicate(true), "armor_plates": int(v.get("armor_plates", 0))}
	var items: Array = []
	var crit := {}
	var remap := {}
	for loc in LOCS:
		var src: Array = v.get("crit_slots", {}).get(loc, [])
		var list: Array = []
		for s in src:
			if s == null or int(s) >= v["items"].size() or v["items"][int(s)] == null:
				continue
			var id := int(v["items"][int(s)])
			if not is_fixed(component(data, id)):
				continue
			if not remap.has(int(s)):
				remap[int(s)] = items.size()
				items.append(id)
			list.append(remap[int(s)])
		for id in p[loc]:
			list.append(items.size())
			items.append(id)
			var ammo := int(component(data, id).get("weapon", {}).get("ammo_id", 0))
			if ammo > 0 and not component(data, ammo).is_empty():
				list.append(items.size())
				items.append(ammo)
		while list.size() < maxi(src.size(), int(STD_SLOTS[loc])):
			list.append(null)
		crit[loc] = list
	return {"name": name, "parts": p, "items": items, "crit_slots": crit, "armor_plates": plates(p)}
