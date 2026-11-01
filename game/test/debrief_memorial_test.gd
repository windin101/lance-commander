extends GdUnitTestSuite
## Debrief: a KIA pilot's row carries the memorial portrait thumbnail; fit pilots have none (LANCE-32 follow-up).


var _last := {}


func before_test() -> void:
	_last = Flow.last_report


func after_test() -> void:
	Flow.last_report = _last


func _debrief(pilots: Array) -> Control:
	var d: Control = auto_free(load("res://scenes/debrief.tscn").instantiate())
	Flow.last_report = {"mission": "mc2_01", "title": "Test", "won": true, "time": 60.0, "objectives": [], "lance": [], "kills": [],
		"losses": 0, "payout": 0, "pilots": pilots, "salvage": []}
	add_child(d)
	return d


func test_kia_pilot_row_shows_the_memorial_thumbnail() -> void:
	var d := _debrief([{"profile": "pmwsteel", "kills": [], "dead": true, "mech": "Werewolf", "variant": "Werewolf Prime"},
		{"profile": "pmwflash", "kills": [], "dead": false, "mech": "Bushwacker", "variant": "Bushwacker Prime"}])
	var kia := d.find_children("KiaPilot", "HBoxContainer", true, false)
	assert_int(kia.size()).is_equal(1)  # only the dead pilot
	var thumb := kia[0].find_child("MemorialThumb", true, false) as TextureRect
	assert_object(thumb).is_not_null()
	assert_object(thumb.texture).is_same(PilotPortraits.memorial_for("pmwsteel"))
	assert_object(thumb.texture).is_not_same(PilotPortraits.texture_for("pmwsteel"))


func test_kia_thumbnail_falls_back_to_the_clean_face_without_a_memorial() -> void:
	var d := _debrief([{"profile": "pmwnobody", "kills": [], "dead": true, "mech": "Werewolf", "variant": "Werewolf Prime"}])
	var thumb := d.find_child("MemorialThumb", true, false) as TextureRect
	assert_object(thumb).is_not_null()
	assert_object(thumb.texture).is_same(PilotPortraits.memorial_for("pmwnobody"))
