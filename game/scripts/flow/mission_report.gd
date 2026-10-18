class_name MissionReport
extends RefCounted
## The debrief's facts, taken from a finished (or abandoned) SimMission. Stored as a
## plain Dictionary so Flow can save it with the campaign.
##
## {mission, title, won, time, objectives: [{title, primary, complete}],
##  lance: [{name, pilot, state, armour}], kills: [{name, count}], losses}


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
			var w_fit: Dictionary = sm.fit.get("Warrior%d" % u.warrior_index, {})
			var pilot: Dictionary = data.pilots.get(String(w_fit.get("Profile", "")).to_lower(), {}).get("General", {})
			lance.append({"name": u.name, "pilot": String(pilot.get("Name", "")), "state": state,
				"armour": roundi(_armour_frac(u) * 100.0)})
		elif u.team != sm.player_team and u.is_disabled():
			kills[u.name] = kills.get(u.name, 0) + 1
	var kill_list := []
	for n in kills:
		kill_list.append({"name": n, "count": kills[n]})
	kill_list.sort_custom(func(a, b): return a["count"] > b["count"])
	return {"mission": sm.world.map.name, "title": title, "won": sm.objectives.result == SimObjectives.Result.WON,
		"time": w.time, "objectives": objectives, "lance": lance, "kills": kill_list, "losses": losses}


static func _armour_frac(u: SimUnit) -> float:
	var cur := 0.0
	var top := 0.0
	for i in u.armor.size():
		cur += u.armor[i]
		top += u.max_armor[i]
	return cur / top if top > 0.0 else 1.0
