extends GdUnitTestSuite
## Comms subtitles: the data (tools/convert/subtitles.py), the on/off setting, timed voice-over
## lines, pilot radio lines by voice, and what the comms panel shows.

const CFG := "user://test_subtitles.cfg"
const FIXTURE := "user://test_subtitles.json"


func before_test() -> void:
	Subtitles.settings_path = CFG
	DirAccess.remove_absolute(ProjectSettings.globalize_path(CFG))
	Subtitles.reset_cache()


func after_test() -> void:
	Subtitles.settings_path = UiStyle.SETTINGS_PATH
	Subtitles.data_path = "res://data/subtitles.json"
	Subtitles.reset_cache()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(CFG))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(FIXTURE))


func _fixture() -> void:
	var f := FileAccess.open(FIXTURE, FileAccess.WRITE)
	f.store_string(JSON.stringify({"vo": {"mc2_12_1": {"speaker": "Cash", "text": "One. Two.", "duration": 4.0,
		"segments": [[0.0, 1.5, "One."], [2.0, 4.0, "Two."]]}},
		"pilots": {"pilot7/plt7_acknowledgea": {"speaker": "FLASH", "voice": "pilot7", "text": "On my way.", "duration": 1.2}}}))
	f.close()
	Subtitles.data_path = FIXTURE
	Subtitles.reset_cache()


func test_the_shipped_data_covers_every_voice_over() -> void:
	var d := Subtitles.data()
	var vo: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))["vo"]
	for k in vo:
		assert_bool(d["vo"].has(k)).override_failure_message(k).is_true()
	assert_int(d["pilots"].size()).is_greater(800)
	assert_str(String(d["_provenance"]["source"])).contains("Shared Source")
	for k in d["pilots"]:
		assert_str(String(d["pilots"][k]["text"])).is_not_empty()


func test_setting_is_on_by_default_and_saved() -> void:
	assert_bool(Subtitles.enabled()).is_true()
	Subtitles.set_enabled(false)
	Subtitles.reset_cache()
	assert_bool(Subtitles.enabled()).is_false()
	var cfg := ConfigFile.new()
	cfg.load(CFG)
	assert_bool(cfg.get_value("comms", "subtitles")).is_false()


func test_voice_over_lines_follow_the_audio() -> void:
	_fixture()
	assert_array(Subtitles.vo_line("mc2_12_1", 0.5)).is_equal(["Cash", "One."])
	assert_array(Subtitles.vo_line("mc2_12_1", 1.8)).is_equal(["Cash", "One."])  # a gap keeps the line up
	assert_array(Subtitles.vo_line("MC2_12_1", 3.0)).is_equal(["Cash", "Two."])
	assert_array(Subtitles.vo_line("nothing", 0.0)).is_equal(["", ""])


func test_pilot_lines_by_voice() -> void:
	_fixture()
	assert_int(Subtitles.voice_of("pmwflash", GameData.pilots)).is_equal(7)  # pilotAudio "pilotg"
	assert_int(Subtitles.voice_of("pmwbubba", GameData.pilots)).is_equal(1)  # "pilotA": the pak names ignore case
	assert_str(Subtitles.pilot_line("pmwflash", "acknowledgeA", GameData.pilots)["text"]).is_equal("On my way.")
	assert_dict(Subtitles.pilot_line("pmwflash", "nothing", GameData.pilots)).is_empty()


func test_comms_panel_shows_the_subtitle_or_the_plain_line() -> void:
	var c: CommsWindow = auto_free(CommsWindow.new())
	add_child(c)
	c.set_voice(true, "Cash", "Two.")
	c._process(0.0)
	assert_bool(c.visible).is_true()
	assert_str(c.caption.text).is_equal("Cash")
	assert_str(c.subtitle.text).is_equal("Two.")
	c.set_voice(true)
	c._process(0.0)
	assert_str(c.caption.text).is_equal("Command")
	assert_str(c.subtitle.text).is_equal("Incoming transmission.")


func test_hud_shows_radio_lines_only_when_on() -> void:
	_fixture()
	var view: Node3D = auto_free(load("res://scenes/mission_view.tscn").instantiate())
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var flash: SimUnit = view.world.units.filter(func(u): return u.pilot_profile == "pmwflash" or (u.is_player and u.pilot and u.pilot.name == "Flash"))[0]
	flash.pilot_profile = "pmwflash"
	assert_bool(view.hud.radio_line(flash, "acknowledgea")).is_true()
	assert_str(view.hud.comms.subtitle.text).is_equal("On my way.")
	assert_object(view.hud.comms.speaker_unit).is_same(flash)
	Subtitles.set_enabled(false, false)
	assert_bool(view.hud.radio_line(flash, "acknowledgea")).is_false()
