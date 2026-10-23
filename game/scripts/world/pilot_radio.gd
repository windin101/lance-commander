class_name PilotRadio
extends RefCounted
## The player's pilots on the radio, as the original ran it (no sim state: it only reads units and events).
##
## Message table: data/audio.json "radio" (Sound/radio.csv, RadioMessageType order). Voices: audio.json
## "pilots"[N] = [[stem, ogg], ...] by packet index (Sound/pilotN.rsp); a profile's pilotAudio letter a-z is
## voice N (Subtitles.voice_of).
##
## Rules, from the Shared Source:
## * Only the player's own pilots speak ("ONLY your pilots speak", warrior.cpp:1335), only while active,
##   and not before the mission's first turn (MechWarrior::radioMessage, warrior.cpp:1289-1331).
## * Per pilot: WEAPONS_OUT once; SENSOR_CONTACT at most every 15 s; UNDER_ATTACK at most every 20 s; the same
##   message type again within 10 s is dropped, except TARGET_ACK, MOVE_BLOCKED and ILLEGAL_ORDER.
##   AMMO_OUT once (Radio::ammoOutPlayed, radio.cpp:131-132).
## * Style: a roll against the row's style chances picks variant A/B/C; the pilot's previous line is not
##   repeated (radio.cpp:134-153). A pilot-identifies-self row is preceded by the callsign packet; the
##   original's roll there never changes the result, so it is always the first callsign (radio.cpp:177-200).
## * Queue (GameSoundSystem::checkMessage / queueRadioMessage, gamesound.cpp:147-280): one line at a time, 8
##   queued, sorted by priority (0 is most urgent). A line is refused while the same pilot has a more urgent
##   one queued, or while anyone has the same type (priority above 1) queued. The same packet queued twice in
##   one tick keeps the newest. Priority 0 (EJECTING, DEATH) cuts off the line playing and that pilot's queue.
##   When a line comes up, queued lines of pilots no longer active are dropped, except DEATH and EJECTING
##   (moveFromQueueToPlaying, gamesound.cpp:160-181). Shelf life is set but never read in the original.

const MAX_QUEUED := 8

var messages: Array = []  # radio.csv rows: {name, priority, shelf_life, styles, chances, pilot_id, map}
var by_name: Dictionary = {}  # "RADIO_ACK" -> RadioMessageType index
var voices: Dictionary = {}  # "N" -> [[stem, path], ...]
var pilots: Dictionary = {}  # GameData.pilots (profile -> FIT blocks), for the voice letter
var queue: Array = []  # entries waiting: {unit, type, msg_id, priority, lines: [[stem, path]], tick}
var current: Dictionary = {}  # the entry playing ({} none)
var rng := RandomNumberGenerator.new()
var _log: Dictionary = {}  # unit id -> {last_type, last_time, last_contact, last_under_fire, weapons_out, ammo_out, last_msg}


func _init(manifest: Dictionary, pilot_profiles: Dictionary, seed_value := 2001) -> void:
	messages = manifest.get("radio", [])
	for i in messages.size():
		by_name[String(messages[i]["name"])] = i
	voices = manifest.get("pilots", {})
	pilots = pilot_profiles
	rng.seed = seed_value


func voice_of(u: SimUnit) -> int:
	return Subtitles.voice_of(u.pilot_profile, pilots)


static func active(u: SimUnit) -> bool:
	return u != null and not u.ejected and not u.is_disabled() and not (u.pilot != null and u.pilot.dead)


func _entry_log(u: SimUnit) -> Dictionary:
	if not _log.has(u.id):
		_log[u.id] = {"last_type": "", "last_time": -1000.0, "last_contact": -1000.0, "last_under_fire": -1000.0,
			"weapons_out": false, "ammo_out": false, "last_msg": -1}
	return _log[u.id]


## MechWarrior::radioMessage + Radio::playMessage: queue message `msg` (a RadioMessageType name) for unit u.
## `dying` lets DEATH and EJECTING through for a pilot who is no longer active. Returns true if queued.
func say(u: SimUnit, msg: String, now: float, tick: int, dying := false) -> bool:
	if u == null or not u.is_player or not by_name.has(msg) or now <= 0.0:
		return false
	if not dying and not active(u):
		return false
	var n := voice_of(u)
	if n == 0 or not voices.has(str(n)):
		return false
	var lg := _entry_log(u)
	match msg:
		"RADIO_WEAPONS_OUT":
			if lg["weapons_out"]:
				return false
			lg["weapons_out"] = true
		"RADIO_SENSOR_CONTACT":
			if float(lg["last_contact"]) > now - 15.0:
				return false
			lg["last_contact"] = now
		"RADIO_UNDER_ATTACK":
			if float(lg["last_under_fire"]) > now - 20.0:
				return false
			lg["last_under_fire"] = now
	var limit := not (msg in ["RADIO_TARGET_ACK", "RADIO_MOVE_BLOCKED", "RADIO_ILLEGAL_ORDER"])
	if limit and lg["last_type"] == msg and float(lg["last_time"]) > now - 10.0:
		return false
	lg["last_time"] = now
	lg["last_type"] = msg
	return _play(u, n, msg, tick)


func _play(u: SimUnit, n: int, msg: String, tick: int) -> bool:
	var info: Dictionary = messages[by_name[msg]]
	var prio := int(info["priority"])
	if not _check(u, prio, msg):
		return false
	var lg := _entry_log(u)
	if msg == "RADIO_AMMO_OUT" and lg["ammo_out"]:
		return false
	var styles := int(info["styles"])
	var i := 0
	if styles > 1:
		var roll := rng.randi_range(0, 99)
		var drop := 0
		while i < styles:
			drop += int(info["chances"][i])
			if roll < drop:
				break
			i += 1
		if i != 0 and i == styles:
			return false
		if int(info["map"]) + i == int(lg["last_msg"]):
			i += 1
		if i >= styles:
			i = 0
	var msg_id := int(info["map"]) + i
	var lines: Array = voices[str(n)]
	var parts: Array = []
	if bool(info["pilot_id"]):
		var cs: Dictionary = messages[by_name["RADIO_CALLSIGN"]]
		var c := int(cs["map"])
		if c < lines.size() and String(lines[c][1]) != "":
			parts.append(lines[c])
	if msg_id >= lines.size() or String(lines[msg_id][1]) == "":
		return false  # this voice never recorded the line (some lack the salvage stems)
	parts.append(lines[msg_id])
	var e := {"unit": u, "type": msg, "msg_id": msg_id, "priority": prio, "lines": parts, "tick": tick}
	if not _queue(e):
		return false
	lg["last_msg"] = msg_id
	if msg == "RADIO_AMMO_OUT":
		lg["ammo_out"] = true
	return true


## GameSoundSystem::checkMessage.
func _check(u: SimUnit, prio: int, msg: String) -> bool:
	for q in queue:
		if (q["unit"] == u and prio > int(q["priority"])) or (int(q["priority"]) > 1 and q["type"] == msg):
			return false
	return true


## GameSoundSystem::queueRadioMessage.
func _queue(e: Dictionary) -> bool:
	for k in range(queue.size() - 1, -1, -1):
		if int(queue[k]["tick"]) == int(e["tick"]) and int(queue[k]["msg_id"]) == int(e["msg_id"]):
			queue.remove_at(k)
	if int(e["priority"]) == 0:
		current = {}
		for k in range(queue.size() - 1, -1, -1):
			if queue[k]["unit"] == e["unit"]:
				queue.remove_at(k)
	var at := queue.size()
	for k in queue.size():
		if int(queue[k]["priority"]) > int(e["priority"]):
			at = k
			break
	if at >= MAX_QUEUED:
		return false
	queue.insert(at, e)
	if queue.size() > MAX_QUEUED:
		queue.resize(MAX_QUEUED)
	return true


## The line that should play now: the current one, or the next from the queue (moveFromQueueToPlaying).
## Call `finished()` when it has played.
func next() -> Dictionary:
	if not current.is_empty():
		return current
	while not queue.is_empty() and not active(queue[0]["unit"]) \
			and not (queue[0]["type"] in ["RADIO_DEATH", "RADIO_EJECTING"]):
		queue.pop_front()
	if queue.is_empty():
		return {}
	current = queue.pop_front()
	return current


func finished() -> void:
	current = {}


# --- what the pilots react to -------------------------------------------------------------------------------

## A sim event (world.events). `world` resolves unit ids.
func on_event(e: Dictionary, world: SimWorld, now: float, tick: int) -> void:
	match String(e["type"]):
		"impact":
			var u: SimUnit = world.units[int(e["unit"])]
			if not u.is_player:
				return
			var form := String(e.get("form", ""))
			if form == "strike":
				say(u, "RADIO_UNDER_AIRSTRIKE", now, tick)  # attackerWID -3 (handleHitByWeaponFire)
			elif form == "mine":
				say(u, "RADIO_HITTING_MINES", now, tick)  # attackerWID -2
			elif int(e.get("from", -1)) >= 0:
				var by: SimUnit = world.units[int(e["from"])]
				if by.team != u.team and u.order_target == null:
					say(u, "RADIO_UNDER_ATTACK", now, tick)  # only when not already ordered at a target
		"disabled":
			var dead: SimUnit = world.units[int(e["unit"])]
			var killer: SimUnit = dead.last_attacker
			if killer != null and killer.is_player and killer.team != dead.team:
				var m := kill_message(dead)
				if m != "":
					say(killer, m, now, tick)
		"ejected":
			say(world.units[int(e["unit"])], "RADIO_EJECTING", now, tick, true)
		"captured":
			var t: SimUnit = world.units[int(e["target"])]
			say(world.units[int(e["unit"])], "RADIO_CAPTURED_BUILDING" if t is SimStructure else "RADIO_CAPTURED_VEHICLE", now, tick)
		"capture_refused", "capture_blocked":
			say(world.units[int(e["unit"])], "RADIO_CANNOT_CAPTURE", now, tick)
		"order_refused":
			if e.has("unit"):
				say(world.units[int(e["unit"])], "RADIO_ILLEGAL_ORDER", now, tick)
		"repair_done":
			say(world.units[int(e["unit"])], "RADIO_REFIT_DONE", now, tick)
		"shot":
			# The taunt: RollDice(1) each time a pilot lets loose at a moving target (warrior.cpp:3643-3646).
			var by: SimUnit = world.units[int(e["from"])]
			var to := int(e.get("to", -1))
			if by.is_player and to >= 0 and world.units[to].is_mover() and not (world.units[to] is SimStructure):
				var lg := _entry_log(by)
				if int(lg.get("volley_tick", -1)) != tick:
					lg["volley_tick"] = tick
					if rng.randi_range(0, 99) < 1:
						say(by, "RADIO_TAUNT", now, tick)


## The kill line (MechWarrior::handleKilledTarget, warrior.cpp:7036-7096): a mech (not a copter) MECH_DEAD, a
## ground vehicle VEHICLE_DEAD unless it is infantry (no path locks), a building BUILDING_DEAD, turrets and
## gates OBJECT_DEAD.
static func kill_message(dead: SimUnit) -> String:
	if dead is SimMech:
		return "RADIO_VEHICLE_DEAD" if dead.flying else "RADIO_MECH_DEAD"
	if dead is SimVehicle:
		if dead.flying:
			return "RADIO_VEHICLE_DEAD"
		return "RADIO_VEHICLE_DEAD" if (dead as SimVehicle).path_locks else ""
	if dead is SimTurret:
		return "RADIO_OBJECT_DEAD"
	if dead is SimStructure:
		return "RADIO_BUILDING_DEAD"
	return "RADIO_OBJECT_DEAD"


## Once per tick: state the sim does not announce as events (player orders, pilot wounds, ammo, weapons).
func poll(world: SimWorld, now: float, tick: int) -> void:
	for u in world.units:
		if not u.is_player or not u.is_mover():
			continue
		var lg := _entry_log(u)
		# Wounds: DEATH (priority 0) when the pilot dies, PILOT_HURT for a wound that does not kill
		# (MechWarrior::injure, warrior.cpp:1960-1985).
		if u.pilot != null:
			var w := u.pilot.wounds
			if lg.has("wounds") and w > float(lg["wounds"]):
				if u.pilot.dead:
					say(u, "RADIO_DEATH", now, tick, true)
				else:
					say(u, "RADIO_PILOT_HURT", now, tick)
			lg["wounds"] = w
		if not active(u):
			continue
		# A player order (origin 0, a new order dict from SimAbl.player_order): the acknowledgement that
		# TacticalOrder::execute and Mover::handleTacticalOrder pick (tacordr.cpp:880-1025, mover.cpp:3233-3237).
		if u.brain != null and "order" in u.brain:
			var o: Dictionary = u.brain.order
			if lg.has("order") and not is_same(o, lg["order"]) and int(o.get("origin", -1)) == 0:
				var m := order_message(o, rng)
				if m != "":
					say(u, m, now, tick)
			lg["order"] = o
		# Ammo and weapons (Mover::reduceAmmo -> AMMO_OUT, calcWeaponEffectiveness 0 -> WEAPONS_OUT).
		var any_working := false
		var dry := false
		for inv in u.weapon_indices():
			var it: Dictionary = u.items[inv]
			var shots := u.weapon_shots(inv)
			if shots == 0:
				dry = true
			if not bool(it.get("disabled", false)) and shots != 0:
				any_working = true
		# on the change only, as the original reports the moment a bin runs dry or the last weapon goes
		if dry and lg.has("dry") and not lg["dry"]:
			say(u, "RADIO_AMMO_OUT", now, tick)
		if not any_working and lg.get("armed", false):
			say(u, "RADIO_WEAPONS_OUT", now, tick)
		lg["dry"] = dry
		lg["armed"] = any_working


## The radio line for a player order (SimAbl order dict), "" for none: attacks 50/50 TARGET_ACK or ACK, an aimed
## shot CALLED_SHOT (it outranks the ack queued with it), guard GUARD, capture ACK; moves, jumps and power
## orders are not acknowledged in the original.
static func order_message(o: Dictionary, r: RandomNumberGenerator) -> String:
	match int(o.get("code", 0)):
		SimAbl.TO_ATTACK_OBJECT:
			if int(o.get("aim", -1)) != -1:
				return "RADIO_CALLED_SHOT"
			return "RADIO_TARGET_ACK" if r.randi_range(0, 99) < 50 else "RADIO_ACK"
		SimAbl.TO_ATTACK_POINT:
			return "RADIO_TARGET_ACK" if r.randi_range(0, 99) < 50 else "RADIO_ACK"
		SimAbl.TO_GUARD:
			return "RADIO_GUARD"
		SimAbl.TO_CAPTURE:
			return "RADIO_ACK"
	return ""
