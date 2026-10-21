class_name Campaign
extends RefCounted
## The campaign between missions (docs/specs/campaign-layer.md): C-Bills, the mech
## inventory with deploy slots and pilots, the pilot roster, bonus technology, and the
## rules that change them. Owned and saved by Flow.
##
## A mech in the inventory: {"id", "chassis", "variant" (CSV variant index: the base
## design, whose fixed items the mech keeps), "pilot" (profile or ""), "slot" (0 reserve,
## 1-12 deployed), "loadout" {"name", "parts" {loc: [component ids]}} (stock or refitted in
## the Mech Lab, Loadout rules)}. Mechs carry no damage: every mech starts every mission
## repaired (7.2).
## A pilot: {"name", "gunnery", "piloting", "kills", "missions", "dead"}.
## Stores: parts stripped in the Mech Lab, {component id: count}; fitting from them is free.
## Saved variants: [{"name", "chassis", "parts"}], loadouts the player named in the lab.
##
## Simplifications: a variant's availability counts only components that some purchase
## file lists (structural parts such as the engine and cockpit are never listed);
## promotions don't offer specialty picks yet.

const START_CBILLS := 80000
const MAX_DEPLOY := 12
const DEFAULT_DROP_LIMIT := 300.0
const SALVAGE_RATE := 0.8
const SKILL_CAP := 80.0
const SKILL_GAIN_CAP := 4.0
const KILL_POINTS := {"light": 45.0, "medium": 60.0, "heavy": 70.0, "assault": 80.0, "vehicle": 20.0}

var data: Object  # GameData
var c_bills := START_CBILLS
var mechs: Array[Dictionary] = []
var pilots: Dictionary = {}  # profile -> pilot
var bonus_files: Array[String] = []
var stores: Dictionary = {}  # component id -> count
var saved_variants: Array[Dictionary] = []  # {name, chassis, parts}
var _next_id := 1
var _universe: Dictionary = {}  # component ids any purchase file lists


static func create(game_data: Object) -> Campaign:
	var c := Campaign.new()
	c.data = game_data
	c.reset()
	return c


func reset() -> void:
	c_bills = START_CBILLS
	mechs.clear()
	bonus_files.clear()
	pilots.clear()
	stores.clear()
	saved_variants.clear()
	_next_id = 1
	var roster: Array = _json("res://data/roster.json", [])
	for p in roster:
		var fit: Dictionary = data.pilots.get(p, {})
		var gen: Dictionary = fit.get("General", {})
		var sk: Dictionary = fit.get("Skills", {})
		pilots[p] = {"name": String(gen.get("Name", p.trim_prefix("pmw").capitalize())),
			"gunnery": float(sk.get("Gunnery", 50)), "piloting": float(sk.get("Piloting", 50)),
			"kills": 0, "missions": 0, "dead": false}


static func _json(path: String, fallback: Variant) -> Variant:
	if not FileAccess.file_exists(path):
		return fallback
	return JSON.parse_string(FileAccess.get_file_as_string(path))


# --- prices and availability (5) ----------------------------------------------------------

func variant(chassis: String, index: int) -> Dictionary:
	var ch: Dictionary = data.chassis.get(chassis, {})
	var vs: Array = ch.get("variants", [])
	return vs[index] if index >= 0 and index < vs.size() else {}


## Variant price = chassis cost + the cost of every component fitted (4.4).
func price(chassis: String, index: int) -> int:
	var ch: Dictionary = data.chassis.get(chassis, {})
	var total := int(ch.get("cbills", 0))
	for id in variant(chassis, index).get("items", []):
		if id != null:  # empty crit slots
			total += int(data.components.get(int(id), {}).get("rp", 0))
	return total


func tonnage(chassis: String) -> float:
	return float(data.chassis.get(chassis, {}).get("tonnage", 0))


func _purchase(name: String) -> Dictionary:
	return _json("res://data/purchase/%s.json" % name.to_lower().get_file().get_basename(), {})


## The mission's purchase file plus every bonus file (5.1).
func _tech(mission: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var main := _purchase(mission_info(mission).get("PurchaseFile", ""))
	if not main.is_empty():
		out.append(main)
	for b in bonus_files:
		out.append(_purchase(b))
	return out


func _component_universe() -> Dictionary:
	if _universe.is_empty():
		for f in DirAccess.get_files_at("res://data/purchase"):
			if f.ends_with(".json"):
				for id in _purchase(f).get("components", []):
					_universe[int(id)] = true
	return _universe


func available_components(mission: String) -> Dictionary:
	var out := {}
	for t in _tech(mission):
		if t.get("all_components", false):
			return {"all": true}
		for id in t.get("components", []):
			out[int(id)] = true
	return out


## Variants for sale: chassis listed and every purchasable-type component available.
func purchasable(mission: String) -> Array[Dictionary]:
	var comps := available_components(mission)
	var universe := _component_universe()
	var out: Array[Dictionary] = []
	var listed := {}
	for t in _tech(mission):
		for m in t.get("mechs", []):
			listed[String(m)] = true
	for chassis in listed:
		if not data.chassis.has(chassis):
			continue
		for v in data.chassis[chassis].get("variants", []):
			if v.get("hidden", false):
				continue
			var ok := true
			if not comps.has("all"):
				for id in v.get("items", []):
					if id != null and universe.has(int(id)) and not comps.has(int(id)):
						ok = false
						break
			if ok:
				out.append({"chassis": chassis, "variant": int(v["index"]), "name": String(v.get("name", chassis)),
					"tonnage": tonnage(chassis), "price": price(chassis, int(v["index"]))})
	out.sort_custom(func(a, b): return a["price"] < b["price"])
	return out


func available_pilots(mission: String) -> Array[String]:
	var listed := {}
	for t in _tech(mission):
		for p in t.get("pilots", []):
			listed[String(p)] = true
	var out: Array[String] = []
	for p in pilots:
		if listed.has(p) and not pilots[p]["dead"]:
			out.append(p)
	return out


# --- mission settings ---------------------------------------------------------------------

func mission_info(mission: String) -> Dictionary:
	var c: Dictionary = _json("res://data/campaign.json", {})
	for k in c:
		if k.contains("Mission") and c[k] is Dictionary and String(c[k].get("FileName", "")).to_lower() == mission:
			return c[k]
	return {}


func plays_logistics(mission: String) -> bool:
	return bool(mission_info(mission).get("PlayLogistics", true))


func drop_limit(mission: String) -> float:
	var fit: Dictionary = _json("res://data/missions/%s.json" % mission, {})
	return float(fit.get("MissionSettings", {}).get("DropWeightLimit", DEFAULT_DROP_LIMIT))


# --- force group (3) ----------------------------------------------------------------------

func deployed() -> Array[Dictionary]:
	var out: Array[Dictionary] = mechs.filter(func(m): return int(m["slot"]) > 0)
	out.sort_custom(func(a, b): return a["slot"] < b["slot"])
	return out


func deployed_tonnage() -> float:
	var t := 0.0
	for m in deployed():
		t += tonnage(m["chassis"])
	return t


func can_deploy(m: Dictionary, mission: String) -> bool:
	return int(m["slot"]) == 0 and deployed().size() < MAX_DEPLOY \
		and deployed_tonnage() + tonnage(m["chassis"]) <= drop_limit(mission) + 0.01


func deploy(m: Dictionary, mission: String) -> bool:
	if not can_deploy(m, mission):
		return false
	var used := {}
	for d in deployed():
		used[int(d["slot"])] = true
	var slot := 1
	while used.has(slot):
		slot += 1
	m["slot"] = slot
	return true


func withdraw(m: Dictionary) -> void:
	m["slot"] = 0
	m["pilot"] = ""  # removing a mech also clears its pilot (3.2)


## Pilots free to assign: available for this mission, not on another deployed mech.
func free_pilots(mission: String) -> Array[String]:
	var used := {}
	for d in deployed():
		if String(d["pilot"]) != "":
			used[String(d["pilot"])] = true
	return available_pilots(mission).filter(func(p): return not used.has(p))


## Drop weight over the limit (a mission with a lower limit), from the top slot down (2.3).
func fit_force(mission: String) -> void:
	var d := deployed()
	while not d.is_empty() and deployed_tonnage() > drop_limit(mission) + 0.01:
		withdraw(d.pop_back())


func launch_problem(mission: String) -> String:
	var d := deployed()
	if d.is_empty():
		return "Deploy at least one 'Mech"
	if deployed_tonnage() > drop_limit(mission) + 0.01:
		return "Over the drop weight"
	for m in d:
		if String(m["pilot"]) == "":
			return "Every deployed 'Mech needs a pilot"
	return ""


## What the mission spawns in place of its own player parts (3.4).
func force() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for m in deployed():
		var p: Dictionary = pilots.get(String(m["pilot"]), {})
		var lo: Dictionary = loadout(m)
		out.append({"chassis": m["chassis"], "variant": int(m["variant"]), "pilot": String(m["pilot"]),
			"gunnery": float(p.get("gunnery", 50)), "piloting": float(p.get("piloting", 50)),
			"loadout": Loadout.to_sim(data, String(m["chassis"]), int(m["variant"]), lo["parts"], String(lo["name"]))})
	return out


# --- buying, selling, salvage (5.2, 6.2) ---------------------------------------------------

## lo: {"name", "parts"} for a refitted mech; empty for the variant's stock loadout.
func add_mech(chassis: String, index: int, pilot := "", slot := 0, lo := {}) -> Dictionary:
	var m := {"id": _next_id, "chassis": chassis, "variant": index, "pilot": pilot, "slot": slot,
		"loadout": _clean_loadout(chassis, index, lo)}
	_next_id += 1
	mechs.append(m)
	return m


func _clean_loadout(chassis: String, index: int, lo: Dictionary) -> Dictionary:
	if lo.is_empty() or not lo.has("parts"):
		return stock_loadout(chassis, index)
	return {"name": String(lo.get("name", variant(chassis, index).get("name", chassis))),
		"parts": Loadout.normalize(lo["parts"])}


func stock_loadout(chassis: String, index: int) -> Dictionary:
	return {"name": String(variant(chassis, index).get("name", chassis)),
		"parts": Loadout.stock_parts(data, chassis, index)}


## A mech's loadout (stock when it has none: a mech made before the lab).
func loadout(m: Dictionary) -> Dictionary:
	if not m.has("loadout") or not (m["loadout"] is Dictionary) or not m["loadout"].has("parts"):
		m["loadout"] = stock_loadout(String(m["chassis"]), int(m["variant"]))
	return m["loadout"]


## What a mech is worth: chassis + fixed items + its parts (4.4); the sale price.
func mech_value(m: Dictionary) -> int:
	return Loadout.value(data, String(m["chassis"]), int(m["variant"]), loadout(m)["parts"])


func buy(chassis: String, index: int) -> bool:
	var cost := price(chassis, index)
	if cost > c_bills:
		return false
	c_bills -= cost
	add_mech(chassis, index)
	return true


func sell(m: Dictionary) -> bool:
	if int(m["slot"]) > 0:
		return false  # only reserve mechs can be sold
	c_bills += mech_value(m)
	mechs.erase(m)
	return true


func salvage_price(chassis: String, index: int) -> int:
	return int(SALVAGE_RATE * price(chassis, index))


func buy_salvage(chassis: String, index: int) -> bool:
	var cost := salvage_price(chassis, index)
	if cost > c_bills:
		return false
	c_bills -= cost
	add_mech(chassis, index)
	return true


# --- Mech Lab (Loadout rules, issue I86) ------------------------------------------------------

## The bill for refitting m to parts with this mission's market (Loadout.quote).
func refit_quote(m: Dictionary, parts: Dictionary, mission: String) -> Dictionary:
	return Loadout.quote(data, loadout(m)["parts"], parts, stores, available_components(mission))


## Why m can't be refitted to parts now, or "".
func refit_problem(m: Dictionary, parts: Dictionary, mission: String) -> String:
	var bad := Loadout.problems(data, String(m["chassis"]), int(m["variant"]), parts)
	if not bad.is_empty():
		return "Illegal loadout: " + bad[0]
	var q := refit_quote(m, parts, mission)
	if not q["unavailable"].is_empty():
		return "%s is not for sale this mission" % Loadout.component(data, int(q["unavailable"][0])).get("name", "?")
	if int(q["cost"]) > c_bills:
		return "Not enough C-Bills"
	return ""


## Refit m: parts that leave go to stores, arriving parts come from stores or are bought.
## Instant (no calendar). name "" keeps a matching variant's name or marks it modified.
func refit(m: Dictionary, parts: Dictionary, mission: String, name := "") -> bool:
	if refit_problem(m, parts, mission) != "":
		return false
	var q := refit_quote(m, parts, mission)
	c_bills -= int(q["cost"])
	stores = q["stores"]
	m["loadout"] = {"name": name if name != "" else loadout_name(m, parts), "parts": Loadout.normalize(parts)}
	return true


## The name a loadout shows: a saved or stock variant it matches, else "<base> (modified)".
func loadout_name(m: Dictionary, parts: Dictionary) -> String:
	var chassis := String(m["chassis"])
	for sv in saved_variants:
		if sv["chassis"] == chassis and Loadout.same(sv["parts"], parts):
			return String(sv["name"])
	for v in Loadout.stock_variants(data.chassis.get(chassis, {})):
		if Loadout.same(Loadout.stock_parts(data, chassis, int(v["index"])), parts) \
				and Loadout.fixed_slots(data, chassis, int(v["index"])) == Loadout.fixed_slots(data, chassis, int(m["variant"])):
			return String(v.get("name", chassis))
	return "%s (modified)" % String(variant(chassis, int(m["variant"])).get("name", chassis))


## Save a loadout under a player name for its chassis (replaces one of the same name).
## Designer variant names are refused.
func save_variant(chassis: String, name: String, parts: Dictionary) -> bool:
	name = name.strip_edges()
	if name.is_empty():
		return false
	for v in data.chassis.get(chassis, {}).get("variants", []):
		if String(v.get("name", "")).to_lower() == name.to_lower():
			return false
	for sv in saved_variants:
		if sv["chassis"] == chassis and String(sv["name"]).to_lower() == name.to_lower():
			sv["parts"] = Loadout.normalize(parts)
			sv["name"] = name
			return true
	saved_variants.append({"name": name, "chassis": chassis, "parts": Loadout.normalize(parts)})
	return true


func variants_for(chassis: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = saved_variants.filter(func(sv): return sv["chassis"] == chassis)
	return out


## Apply a saved variant to another mech of its chassis (a refit at its cost).
func apply_variant(m: Dictionary, sv: Dictionary, mission: String) -> bool:
	if String(sv.get("chassis", "")) != String(m["chassis"]):
		return false
	return refit(m, sv["parts"], mission, String(sv["name"]))


# --- after a mission (7, 8.3, 9) -----------------------------------------------------------

## Apply a won mission's report: objective pay, the force group replaced by the mechs
## that walked out (repaired), pilots updated (kills, skills, deaths).
func apply_win(report: Dictionary) -> void:
	c_bills += int(report.get("payout", 0))
	for m in deployed():
		mechs.erase(m)
	var slot := 1
	for s in report.get("survivors", []):
		if data.chassis.has(String(s["chassis"])):
			add_mech(String(s["chassis"]), int(s["variant"]), String(s.get("pilot", "")), slot, s.get("loadout", {}))
			slot += 1
	for p in report.get("pilots", []):
		var pd: Dictionary = pilots.get(String(p["profile"]), {})
		if pd.is_empty():
			continue
		if p.get("dead", false):
			pd["dead"] = true
			continue
		var gain_g := 0.0
		for k in p.get("kills", []):
			gain_g += 0.01 * float(KILL_POINTS.get(String(k), 0.0))
			pd["kills"] = int(pd["kills"]) + 1
		pd["gunnery"] = minf(SKILL_CAP, float(pd["gunnery"]) + minf(gain_g, SKILL_GAIN_CAP))
		pd["piloting"] = minf(SKILL_CAP, float(pd["piloting"]) + 1.0)
		pd["missions"] = int(pd["missions"]) + 1
	for b in report.get("bonus_files", []):
		if not bonus_files.has(String(b)):
			bonus_files.append(String(b))


## Rank from the average of gunnery and piloting (8.4).
static func rank(p: Dictionary) -> String:
	var avg := (float(p.get("gunnery", 50)) + float(p.get("piloting", 50))) / 2.0
	if avg > 79.0:
		return "Ace"
	if avg > 70.0:
		return "Elite"
	if avg > 60.0:
		return "Veteran"
	if avg > 50.0:
		return "Regular"
	return "Green"


# --- save ----------------------------------------------------------------------------------

func to_dict() -> Dictionary:
	var st := {}
	for id in stores:
		st[str(id)] = int(stores[id])
	return {"c_bills": c_bills, "mechs": mechs, "pilots": pilots, "bonus_files": bonus_files, "next_id": _next_id,
		"stores": st, "saved_variants": saved_variants}


func from_dict(d: Dictionary) -> void:
	c_bills = int(d.get("c_bills", START_CBILLS))
	mechs.clear()
	for m in d.get("mechs", []):
		# Saves from before the Mech Lab hold a variant index only: that variant's stock loadout.
		mechs.append({"id": int(m["id"]), "chassis": String(m["chassis"]), "variant": int(m["variant"]),
			"pilot": String(m.get("pilot", "")), "slot": int(m.get("slot", 0)),
			"loadout": _clean_loadout(String(m["chassis"]), int(m["variant"]), m.get("loadout", {}))})
	for p in d.get("pilots", {}):
		if pilots.has(p):
			pilots[p].merge(d["pilots"][p], true)
	bonus_files.clear()
	for b in d.get("bonus_files", []):
		bonus_files.append(String(b))
	_next_id = int(d.get("next_id", mechs.size() + 1))
	stores.clear()
	var st: Dictionary = d.get("stores", {})
	for id in st:
		if int(st[id]) > 0:
			stores[int(id)] = int(st[id])
	saved_variants.clear()
	for sv in d.get("saved_variants", []):
		if sv is Dictionary and sv.has("parts"):
			saved_variants.append({"name": String(sv.get("name", "")), "chassis": String(sv.get("chassis", "")),
				"parts": Loadout.normalize(sv["parts"])})
