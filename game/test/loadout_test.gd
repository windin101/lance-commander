extends GdUnitTestSuite
## Mech Lab fitting rules (Loadout, issue I86): derived hardpoints, slots and structure,
## every stock design legal under the rules, each refusal, the refit bill with stores, and
## the sim spawning exactly the loadout the campaign gives it.

const AC5 := 100
const AC10 := 101
const AC20 := 102
const MG := 114
const LRM5 := 120
const PPC := 145
const LASER := 156
const SINK := 7
const JETS := 10
const PLATE := 25


func _bush() -> Dictionary:
	return Loadout.stock_parts(GameData, "bushwacker", 0)


## Every non-hidden stock variant of every 'Mech chassis passes every rule (the lab's own
## acceptance test: no designer 'Mech starts illegal), and the heaviest is exactly full.
func test_every_stock_variant_is_legal() -> void:
	var checked := 0
	for chassis in GameData.chassis:
		if not Loadout.lab_allowed(GameData, chassis):
			continue
		var heaviest := 0.0
		for v in Loadout.stock_variants(GameData.chassis[chassis]):
			var parts := Loadout.stock_parts(GameData, chassis, int(v["index"]))
			var bad := Loadout.problems(GameData, chassis, int(v["index"]), parts)
			assert_array(bad).override_failure_message("%s / %s: %s" % [chassis, v["name"], bad]).is_empty()
			heaviest = maxf(heaviest, Loadout.tons(GameData, chassis, parts))
			checked += 1
		assert_float(heaviest).override_failure_message(chassis).is_equal_approx(Loadout.info(GameData, chassis)["tonnage"], 0.001)
	assert_int(checked).is_equal(29)  # 34 chassis less the four 'Copters and the scripted Talon


## Each stock part fits back into the location it came from (fits() agrees with problems()).
func test_every_stock_part_refits_where_it_was() -> void:
	for chassis in GameData.chassis:
		if not Loadout.lab_allowed(GameData, chassis):
			continue
		for v in Loadout.stock_variants(GameData.chassis[chassis]):
			var parts := Loadout.stock_parts(GameData, chassis, int(v["index"]))
			for loc in Loadout.LOCS:
				for i in parts[loc].size():
					var less := Loadout.copy(parts)
					var id: int = less[loc].pop_at(i)
					assert_str(Loadout.fits(GameData, chassis, int(v["index"]), less, id, loc)) \
						.override_failure_message("%s %s %d" % [chassis, loc, id]).is_empty()


func test_bushwacker_hardpoints_structure_and_slots() -> void:
	var inf := Loadout.info(GameData, "bushwacker")
	var hp: Dictionary = inf["hardpoints"]
	assert_dict(hp["larm"]).is_equal({"B": 1, "E": 0, "M": 0})
	assert_dict(hp["ctorso"]).is_equal({"B": 1, "E": 0, "M": 0})
	assert_dict(hp["rarm"]).is_equal({"B": 0, "E": 1, "M": 0})
	assert_dict(hp["ltorso"]).is_equal({"B": 0, "E": 0, "M": 3})
	assert_dict(hp["rtorso"]).is_equal({"B": 2, "E": 0, "M": 0})
	assert_dict(hp["head"]).is_equal({"B": 0, "E": 0, "M": 0})
	assert_float(inf["structure"]).is_equal_approx(17.0, 0.001)  # 55 t less a 38 t payload
	assert_bool(inf["jump_jets"]).is_false()
	assert_float(inf["base_armor"]).is_equal(112.0)
	var fixed := Loadout.fixed_slots(GameData, "bushwacker", 0)
	assert_int(fixed["ctorso"]).is_equal(10)  # engine 6 + gyro 4
	assert_int(fixed["larm"]).is_equal(4)  # shoulder + arm actuator
	assert_int(inf["slots"]["ctorso"]).is_equal(12)
	assert_int(inf["slots"]["head"]).is_equal(6)
	# A stock design over the standard count raises that location's capacity.
	assert_int(Loadout.info(GameData, "atlas")["slots"]["rtorso"]).is_equal(20)
	assert_int(Loadout.info(GameData, "jaegermech")["slots"]["larm"]).is_equal(16)


func test_stock_bushwacker_stats() -> void:
	var s := Loadout.stats(GameData, "bushwacker", _bush())
	assert_float(s["tons"]).is_equal_approx(55.0, 0.001)
	assert_float(s["alpha"]).is_equal_approx(25.0, 0.001)
	assert_float(s["heat"]).is_equal(18.0)
	assert_float(s["heat_cap"]).is_equal(27.0)
	assert_float(s["armor"]).is_equal(144.0)  # 112 + one plate
	assert_int(s["speed"]).is_equal(86)
	assert_int(s["range"]).is_equal(3)  # LRMs
	assert_int(Loadout.value(GameData, "bushwacker", 0, _bush())).is_equal(Campaign.create(GameData).price("bushwacker", 0))


func test_refusals() -> void:
	var p := _bush()
	# Full stock 'Mech: nothing more fits by weight.
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, SINK, "rtorso")).contains("Too heavy")
	# Location map: no weapons in the head.
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, MG, "head")).contains("can't go in the head")
	# Hardpoints: no energy hardpoint in the left torso, missile ones all used.
	p["ltorso"].pop_back()
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, PPC, "ltorso")).contains("no free energy hardpoint")
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, LRM5, "ltorso")).is_empty()
	# Slots: the AC/20 needs 12, the left arm has 8 once the AC/10 is out.
	p["larm"].clear()
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, AC20, "larm")).contains("Not enough slots")
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, AC5, "larm")).is_empty()
	# Jump jets: not on the Bushwacker; on the Hunchback, legs only.
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, JETS, "lleg")).contains("can't mount jump jets")
	var h := Loadout.stock_parts(GameData, "hunchback", 0)
	for loc in Loadout.LOCS:
		h[loc] = h[loc].filter(func(id): return id != JETS)
	assert_str(Loadout.fits(GameData, "hunchback", 0, h, JETS, "rleg")).is_empty()
	assert_str(Loadout.fits(GameData, "hunchback", 0, h, JETS, "larm")).contains("can't go")
	# Fixed items and ammo are never parts.
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, 201, "larm")).contains("can't be fitted")


func test_armour_plating_stops_at_the_maximum() -> void:
	var p := _bush()
	for loc in Loadout.LOCS:
		p[loc] = p[loc].filter(func(id): return id == PLATE)  # strip every weapon: 34 t free
	# 112 base, max 272: five plates in all.
	for i in 4:
		assert_str(Loadout.fits(GameData, "bushwacker", 0, p, PLATE, "ltorso")).is_empty()
		p["ltorso"].append(PLATE)
	assert_float(Loadout.stats(GameData, "bushwacker", p)["armor"]).is_equal(272.0)
	assert_str(Loadout.fits(GameData, "bushwacker", 0, p, PLATE, "rtorso")).contains("maximum")


func test_overheating_is_allowed() -> void:
	var p := Loadout.stock_parts(GameData, "ryoken", 0)
	for loc in Loadout.LOCS:
		p[loc] = p[loc].filter(func(id): return id != SINK)
	var s := Loadout.stats(GameData, "ryoken", p)
	assert_float(s["heat"]).is_greater(s["heat_cap"])
	assert_array(Loadout.problems(GameData, "ryoken", 0, p)).is_empty()


func test_quote_uses_stores_then_market() -> void:
	var old := _bush()
	var p := Loadout.copy(old)
	p["larm"] = [AC5]  # AC/10 out, AC/5 in
	p["ltorso"] = [LRM5, LRM5]
	p["rtorso"] = [MG, MG, LRM5]  # a missile weapon can't go there, but quote doesn't judge rules
	var q := Loadout.quote(GameData, old, p, {AC5: 1}, {"all": true})
	assert_int(q["cost"]).is_equal(0)  # the AC/5 came from stores; the LRM only moved
	assert_dict(q["from_stores"]).is_equal({AC5: 1})
	assert_dict(q["to_stores"]).is_equal({AC10: 1})
	assert_dict(q["stores"]).is_equal({AC10: 1})
	var q2 := Loadout.quote(GameData, old, p, {}, {MG: true})
	assert_int(q2["cost"]).is_equal(int(GameData.components[AC5]["rp"]))
	assert_dict(q2["bought"]).is_equal({AC5: 1})
	assert_array(q2["unavailable"]).is_equal([AC5])


func test_to_sim_is_the_variant_for_stock_and_adds_ammo_for_refits() -> void:
	var v: Dictionary = GameData.chassis["bushwacker"]["variants"][0]
	var stock := Loadout.to_sim(GameData, "bushwacker", 0, _bush())
	assert_array(stock["items"]).is_equal(v["items"])
	assert_dict(stock["crit_slots"]).is_equal(v["crit_slots"])
	var p := _bush()
	p["larm"] = [AC5]
	p["ctorso"] = [MG]  # plate removed
	var s := Loadout.to_sim(GameData, "bushwacker", 0, p, "Hacksaw's")
	assert_int(s["armor_plates"]).is_equal(0)
	assert_str(s["name"]).is_equal("Hacksaw's")
	var ids: Array = s["items"]
	assert_bool(ids.has(AC5) and ids.has(200)).is_true()  # AC/5 and its ammo
	assert_bool(ids.has(AC10) or ids.has(201)).is_false()
	assert_int(ids.count(220)).is_equal(3)  # one LRM bin per rack
	assert_int(ids.count(1)).is_equal(1)  # the engine stays
	var larm: Array = s["crit_slots"]["larm"].filter(func(x): return x != null).map(func(x): return ids[x])
	assert_array(larm).contains([AC5, 200, 33, 4])
	assert_int(s["crit_slots"]["head"].size()).is_equal(6)


## The sim builds a deployed 'Mech from its campaign loadout, not its variant.
func test_force_spawns_the_refitted_loadout() -> void:
	var p := _bush()
	p["larm"] = [AC5, SINK]
	p["rarm"] = [LASER]
	var lo := Loadout.to_sim(GameData, "bushwacker", 0, p, "Hacksaw's")
	var force := [{"chassis": "bushwacker", "variant": 0, "pilot": "pmwhacksaw", "gunnery": 50.0, "piloting": 50.0, "loadout": lo},
		{"chassis": "bushwacker", "variant": 0, "pilot": "pmwflash", "gunnery": 50.0, "piloting": 50.0}]
	var sm := SimMission.load_mission(GameData, "mc2_02", 1, false, force)
	var lance := sm.world.units.filter(func(u): return u.team == 0 and u.commander == 0 and u.is_mover())
	assert_int(lance.size()).is_equal(2)
	var refit: SimMech = lance[0]
	var stock: SimMech = lance[1]
	assert_str(refit.variant_name).is_equal("Hacksaw's")
	var fitted := {}
	for it in refit.items:
		if Loadout.is_part(it["component"]):
			var k := "%d@%s" % [it["master_id"], SimMech.BODY_KEYS[it["body_location"]]]
			fitted[k] = int(fitted.get(k, 0)) + 1
	var want := {}
	for loc in Loadout.LOCS:
		for id in p[loc]:
			if id == PLATE:
				continue  # plating is armour (armor_plates), not an item
			var k := "%d@%s" % [id, loc]
			want[k] = int(want.get(k, 0)) + 1
	assert_dict(fitted).is_equal(want)
	assert_int(refit.items.filter(func(it): return it["master_id"] == 200).size()).is_equal(1)
	assert_int(refit.items.filter(func(it): return it["master_id"] == 201).size()).is_equal(0)
	assert_float(SimHeat.dissipation(sm.world.rules, refit)).is_greater(SimHeat.dissipation(sm.world.rules, stock))  # the sink
	assert_dict(refit.loadout["parts"]).is_equal(p)
	# The stock one is the variant exactly.
	var direct := SimMech.from_chassis(GameData.chassis["bushwacker"], 0, sm.world.rules, null)
	assert_array(stock.items.map(func(it): return it["master_id"])).is_equal(direct.items.map(func(it): return it["master_id"]))
	var armour := 0.0
	for a in refit.max_armor:
		armour += a
	assert_float(armour).is_equal_approx(144.0, 0.5)  # 112 + the plate kept in the centre torso (shares sum to 0.99)
	assert_str(stock.variant_name).is_equal("Bushwacker Prime")
	# Survivors carry the loadout home.
	var r := MissionReport.from_sim(sm, "t", GameData)
	assert_dict(r["survivors"][0]["loadout"]["parts"]).is_equal(p)
