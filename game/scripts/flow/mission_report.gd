class_name MissionReport
extends RefCounted
## The debrief's facts, taken from a finished (or abandoned) SimMission. Stored as a
## plain Dictionary so Flow can save it with the campaign.
##
## {mission, title, won, time, objectives: [{title, primary, complete}],
##  lance: [{name, pilot, state, armour}], kills: [{name, count}], losses,
##  and for the campaign (campaign-layer.md 7-9): payout (C-Bills from objectives),
##  survivors [{chassis, variant, pilot, loadout?}], salvage [{chassis, variant, name}],
##  pilots [{profile, kills: [weight class], dead, mech, variant}], bonus_files}


static func from_sim(sm: SimMission, title: String, data: Object) -> Dictionary:
	var w := sm.world
	var objectives := []
	for obj in sm.objectives.objectives:
		if obj["hidden"]:
			continue
		objectives.append({"title": String(obj["title"]).strip_edges(), "primary": obj["primary"], "complete": obj["complete"]})
	var lance := []
	var losses := 0
	var kills := {}
	for u in w.units:
		if not u.is_mover():
			continue
		if u.team == sm.player_team and u.commander == 0:
			var state := "Operational"
			if u.is_destroyed():
				state = "Destroyed"
			elif u.is_disabled():
				state = "Disabled"
			elif _armour_frac(u) < 0.6:
				state = "Damaged"
			if u.is_disabled():
				losses += 1
			var profile := u.pilot_profile
			if profile == "":
				profile = String(sm.fit.get("Warrior%d" % u.warrior_index, {}).get("Profile", "")).to_lower()
			var pilot: Dictionary = data.pilots.get(profile, {}).get("General", {})
			lance.append({"name": u.name, "pilot": String(pilot.get("Name", "")), "state": state,
				"armour": roundi(_armour_frac(u) * 100.0)})
		elif u.team != sm.player_team and u.is_disabled():
			kills[u.name] = kills.get(u.name, 0) + 1
	var survivors := []
	var pilots := []
	var salvage := []
	for u in w.units:
		if not (u is SimMech) or not u.exists:
			continue
		if u.team == sm.player_team and u.commander == 0 and not u.hulk:
			if not u.is_disabled() and data.chassis.has(u.model):
				var s := {"chassis": u.model, "variant": u.variant, "pilot": u.pilot_profile}
				if not u.loadout.is_empty():
					s["loadout"] = u.loadout.duplicate(true)  # a Mech Lab refit walks out as it went in
				survivors.append(s)
			if u.pilot_profile != "":
				pilots.append({"profile": u.pilot_profile, "kills": sm.kills.get(u.id, []), "dead": u.pilot.dead,
					"mech": u.name, "variant": u.variant_name})
		if u.is_disabled() and not u.is_destroyed() and data.chassis.has(u.model):
			var v: Array = data.chassis[u.model].get("variants", [])
			salvage.append({"chassis": u.model, "variant": u.variant,
				"name": String(v[u.variant].get("name", u.model)) if u.variant < v.size() else u.model})
	var payout := 0
	if sm.objectives.result == SimObjectives.Result.WON:
		for obj in sm.objectives.objectives:
			if obj["complete"]:
				payout += int(obj.get("resource_points", 0))
	var kill_list := []
	for n in kills:
		kill_list.append({"name": n, "count": kills[n]})
	kill_list.sort_custom(func(a, b): return a["count"] > b["count"])
	return {"mission": sm.world.map.name, "title": title, "won": sm.objectives.result == SimObjectives.Result.WON,
		"time": w.time, "objectives": objectives, "lance": lance, "kills": kill_list, "losses": losses,
		"payout": payout, "survivors": survivors, "salvage": salvage, "pilots": pilots,
		"bonus_files": sm.objectives.bonus_files.duplicate()}


static func _armour_frac(u: SimUnit) -> float:
	var cur := 0.0
	var top := 0.0
	for i in u.armor.size():
		cur += u.armor[i]
		top += u.max_armor[i]
	return cur / top if top > 0.0 else 1.0
