extends GdUnitTestSuite
## Audio: manifest integrity, music selection, event-driven playback, VO cues.

func test_manifest_streams_load() -> void:
	var m: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))
	assert_int(m["weapons"].size()).is_greater(30)
	for cat in ["weapons", "sfx", "music", "vo", "betty"]:
		for k in m[cat]:
			var s = load(m[cat][k])
			assert_object(s).override_failure_message("%s/%s" % [cat, k]).is_not_null()
			assert_bool(s is AudioStream).is_true()
	# every slice weapon has a firing sound
	var sm := SimMission.load_mission(GameData, "mc2_01")
	for u in sm.world.units:
		for w in u.weapon_indices():
			var has_sound: bool = m["weapons"].has(str(int(u.items[w]["master_id"])))
			assert_bool(has_sound).override_failure_message("no fire sound for %s" % u.items[w]["component"]["name"]).is_true()


func test_flamer_has_its_own_fire_sound() -> void:
	# Effects.csv row 0 says 3 in its first cell; the converter once keyed by it and the
	# flamer (effect id 3, component 155) lost its sound.
	var m: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))
	assert_str(String(m["weapons"].get("155", ""))).ends_with("sfx_flamer_fire.ogg")


func test_music_selection_follows_mission_script() -> void:
	var R := SimObjectives.Result
	assert_int(AudioDirector.choose_tune(R.PLAYING, false, false)).is_equal(AudioDirector.TUNE_START)
	assert_int(AudioDirector.choose_tune(R.PLAYING, false, true)).is_equal(AudioDirector.TUNE_AMBIENT)
	assert_int(AudioDirector.choose_tune(R.PLAYING, true, true)).is_equal(AudioDirector.TUNE_COMBAT)
	assert_int(AudioDirector.choose_tune(R.WON, true, true)).is_equal(AudioDirector.TUNE_WON)
	assert_int(AudioDirector.choose_tune(R.LOST, false, true)).is_equal(AudioDirector.TUNE_LOST)


func test_shot_plays_weapon_sound_and_vo_schedules() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var w: SimWorld = view.world
	var shooter: SimUnit = w.units[0]
	var target: SimUnit = w.units.filter(func(u): return u is SimMech and u.team != 0)[0]
	var wpn: int = shooter.weapon_indices()[0]
	view._audio_event({"type": "shot", "from": shooter.id, "to": target.id, "weapon": wpn, "form": "EnergyWeapon", "hit": true, "location": 1, "flight": 0.0})
	var path: String = view.audio.manifest["weapons"][str(int(shooter.items[wpn]["master_id"]))]
	assert_bool(view.audio._recent.has(path)).is_true()
	assert_float(view.audio.last_combat_time).is_equal(w.time)
	view.audio.say_later("tut_1e", 2.0, 10.0)
	view.audio.tick(11.0)
	assert_int(view.audio._scheduled.size()).is_greater(0)
	view.audio.tick(12.5)
	assert_bool(view.audio._scheduled.filter(func(s): return s[1] == "tut_1e").is_empty()).is_true()
	view.queue_free()


func test_starslayer_attack_sets_bandits_flag() -> void:
	# mc2_01_starslayer.abl's attack state sets the mission eternal; SimAbl mirrors it.
	var sm := SimMission.load_mission(GameData, "mc2_01", 3)
	var ss: SimUnit = sm.world.units.filter(func(u): return u.brain_name == "mc2_01_Starslayer")[0]
	sm.step()  # the mission script's init clears its flags on its first run
	ss.brain.inst.state = "attack"
	ss.brain.next_brain = 0.0
	for i in 3:
		sm.step()
	assert_bool(sm.world.flags.get("bandits_equipped_trigger", false)).is_true()


func test_mission_script_voice_and_music_events() -> void:
	var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	view._audio_event({"type": "abl_wave", "file": "data\\sound\\mc2_01.WAV"})
	assert_bool(view.audio.voice.playing).is_true()
	assert_bool(view.sm.abl.voice_busy.call()).is_true()  # the script's isPlayingVoiceOver
	view._audio_event({"type": "abl_music", "id": 25})
	assert_int(view.audio.current_tune).is_equal(25)
	view.queue_free()
