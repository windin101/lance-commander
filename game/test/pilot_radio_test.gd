extends GdUnitTestSuite
## The pilots' radio (PilotRadio, AudioDirector): converted voices, the original's throttles and queue, and
## the events and orders that make a pilot speak.

var _m: Dictionary


func before() -> void:
	_m = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))


func _voiced_player(sm: SimMission) -> SimUnit:
	for u in sm.world.units:
		if u.is_player and u.is_mover() and Subtitles.voice_of(u.pilot_profile, GameData.pilots) > 0:
			return u
	return null


func test_voices_and_message_table_converted() -> void:
	assert_int(_m["pilots"].size()).is_equal(26)
	var names: Array = _m["radio"].map(func(r): return r["name"])
	assert_int(names.size()).is_equal(31)  # RadioMessageType, RADIO_ACK .. RADIO_ARMORHOLE
	assert_str(names[0]).is_equal("RADIO_ACK")
	assert_str(names[14]).is_equal("RADIO_UNDER_ATTACK")
	assert_int(int(_m["radio"][14]["map"])).is_equal(19)
	var loaded := 0
	for n in _m["pilots"]:
		var lines: Array = _m["pilots"][n]
		assert_int(lines.size()).is_equal(42)
		assert_str(String(lines[19][0])).is_equal("underattacka")
		for l in lines:
			if String(l[1]) != "":
				assert_bool(load(String(l[1])) is AudioStream).override_failure_message(String(l[1])).is_true()
				loaded += 1
	assert_int(loaded).is_greater(1050)


func test_throttles_follow_the_original() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u := _voiced_player(sm)
	assert_object(u).is_not_null()
	var r := PilotRadio.new(_m, GameData.pilots)
	assert_bool(r.say(u, "RADIO_UNDER_ATTACK", 0.0, 0)).is_false()  # nothing before the first turn
	assert_bool(r.say(u, "RADIO_UNDER_ATTACK", 5.0, 50)).is_true()
	r.queue.clear()
	assert_bool(r.say(u, "RADIO_UNDER_ATTACK", 20.0, 200)).is_false()  # 20 s between "under attack"
	assert_bool(r.say(u, "RADIO_UNDER_ATTACK", 26.0, 260)).is_true()
	r.queue.clear()
	assert_bool(r.say(u, "RADIO_GUARD", 30.0, 300)).is_true()
	r.queue.clear()
	assert_bool(r.say(u, "RADIO_GUARD", 35.0, 350)).is_false()  # same type within 10 s
	assert_bool(r.say(u, "RADIO_ILLEGAL_ORDER", 36.0, 360)).is_true()
	r.queue.clear()
	assert_bool(r.say(u, "RADIO_ILLEGAL_ORDER", 37.0, 370)).is_true()  # exempt from the 10 s rule
	r.queue.clear()
	assert_bool(r.say(u, "RADIO_WEAPONS_OUT", 40.0, 400)).is_true()
	r.queue.clear()
	assert_bool(r.say(u, "RADIO_WEAPONS_OUT", 90.0, 900)).is_false()  # once
	# enemies never speak
	var enemy: SimUnit = sm.world.units.filter(func(x): return not x.is_player and x.is_mover())[0]
	assert_bool(r.say(enemy, "RADIO_UNDER_ATTACK", 100.0, 1000)).is_false()


func test_queue_priorities_and_eject_cuts_in() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var u := _voiced_player(sm)
	var r := PilotRadio.new(_m, GameData.pilots)
	assert_bool(r.say(u, "RADIO_UNDER_ATTACK", 5.0, 50)).is_true()  # priority 1
	assert_bool(r.say(u, "RADIO_TAUNT", 5.5, 55)).is_false()  # 4: this pilot has something more urgent queued
	var first := r.next()
	assert_str(String(first["type"])).is_equal("RADIO_UNDER_ATTACK")
	# pilot-identifies-self: the callsign plays first, then the line
	assert_int((first["lines"] as Array).size()).is_equal(2)
	assert_str(String(first["lines"][0][0])).starts_with("callsign")
	assert_str(String(first["lines"][1][0])).starts_with("underattack")
	assert_bool(r.say(u, "RADIO_EJECTING", 6.0, 60, true)).is_true()  # priority 0 cuts the line off
	assert_bool(r.current.is_empty()).is_true()
	assert_str(String(r.next()["type"])).is_equal("RADIO_EJECTING")


func test_orders_and_events_make_pilots_speak() -> void:
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var w := sm.world
	var u := _voiced_player(sm)
	var r := PilotRadio.new(_m, GameData.pilots)
	var enemy: SimUnit = w.units.filter(func(x): return x.team != u.team and x.is_mover() and x.exists)[0]
	r.poll(w, 1.0, 10)  # first look: remembers the current order, says nothing
	assert_int(r.queue.size()).is_equal(0)
	assert_bool(sm.abl != null and u.brain is SimAbl.Pilot).override_failure_message("player pilots have pbrains").is_true()
	if sm.abl and u.brain is SimAbl.Pilot:
		sm.abl.player_order(u, "attack", enemy)
		r.poll(w, 1.1, 11)
		assert_int(r.queue.size()).is_equal(1)
		assert_bool(r.queue[0]["type"] in ["RADIO_ACK", "RADIO_TARGET_ACK"]).is_true()
		r.queue.clear()
		sm.abl.player_order(u, "attack", enemy, {"aim": 1})
		r.poll(w, 12.0, 120)
		assert_str(String(r.queue[0]["type"])).is_equal("RADIO_CALLED_SHOT")
		r.queue.clear()
	# a kill: the killer reports what it destroyed
	enemy.last_attacker = u
	r.on_event({"type": "disabled", "unit": enemy.id, "destroyed": true}, w, 30.0, 300)
	assert_str(String(r.queue[0]["type"])).is_equal(PilotRadio.kill_message(enemy))
	r.queue.clear()
	# mines and air strikes
	r.on_event({"type": "impact", "unit": u.id, "from": -1, "form": "mine", "location": 0, "damage": 1.0}, w, 50.0, 500)
	assert_str(String(r.queue[0]["type"])).is_equal("RADIO_HITTING_MINES")
	assert_str(PilotRadio.kill_message(SimStructure.new())).is_equal("RADIO_BUILDING_DEAD")


func test_mission_plays_the_line_and_shows_it() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var w: SimWorld = view.world
	var u := _voiced_player(view.sm)
	var heard: Array = []
	view.audio.radio_line.connect(func(unit, stem): heard.append([unit, stem]))
	w.time = maxf(w.time, 5.0)
	view.audio.radio_event({"type": "impact", "unit": u.id, "from": -1, "form": "mine", "location": 0, "damage": 1.0}, w)
	view.audio.radio_poll(w)
	assert_bool(view.audio.radio_player.playing).is_true()
	# the callsign plays first; when it ends, the message
	view.audio.radio_player.stop()
	view.audio.radio_poll(w)
	assert_int(heard.size()).is_equal(1)
	assert_object(heard[0][0]).is_same(u)
	assert_str(String(heard[0][1])).is_equal("hittingmines")
	# and once that ends the line is done: it never plays again
	view.audio.radio_player.stop()
	view.audio.radio_poll(w)
	view.audio.radio_poll(w)
	assert_int(heard.size()).is_equal(1)
	assert_bool(view.audio.radio.current.is_empty()).is_true()
	assert_bool(view.audio.radio_player.playing).is_false()
	view.queue_free()
