class_name AudioDirector
extends Node
## Mission audio from data/audio.json: positional SFX (weapon fire, hits,
## explosions, footsteps), music following the original mission script's
## selection (Missions/mc2_01.abl l.279-433, sndconst.abi), voice-overs from the
## mission's brain config, Betty announcements, and the player's pilots on the radio (PilotRadio: which
## events make them speak and how the original throttled them). Voice and radio duck the music.

const POOL := 24
const COMBAT_HOLD := 10.0  # seconds without combat before music returns to ambient
# sndconst.abi tune ids used by mc2_01.abl.
const TUNE_START := 1
const TUNE_LOST := 8
const TUNE_WON := 9
const TUNE_COMBAT := 14
const TUNE_AMBIENT := 25

var manifest: Dictionary = {}
var music: AudioStreamPlayer
var voice: AudioStreamPlayer
var betty: AudioStreamPlayer
var current_tune := -1
var start_tune_done := false
var last_combat_time := -100.0
var _pool: Array[AudioStreamPlayer3D] = []
var _next := 0
var _cache := {}
var _recent := {}  # stream path -> last play time (ms), throttles volleys
var _voice_queue: Array = []
var _scheduled: Array = []  # [time, vo name]
var radio_player: AudioStreamPlayer
var radio: PilotRadio  # set by setup_radio (a mission); null in bare scenes
var _radio_parts: Array = []  # fragments left of the line playing: [[stem, path]]
var _radio_line: Dictionary = {}

## A pilot's line has started (the message part, after any callsign): unit and stem ("underattacka").
signal radio_line(unit: SimUnit, stem: String)


func _ready() -> void:
	manifest = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio.json"))
	for bus in ["Music", "SFX", "Voice"]:
		if AudioServer.get_bus_index(bus) == -1:
			AudioServer.add_bus()
			AudioServer.set_bus_name(AudioServer.bus_count - 1, bus)
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), -9.0)
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("SFX"), -4.0)
	for i in POOL:
		var p := AudioStreamPlayer3D.new()
		p.bus = "SFX"
		p.unit_size = 40.0
		p.max_distance = 900.0
		p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
		add_child(p)
		_pool.append(p)
	music = AudioStreamPlayer.new()
	music.bus = "Music"
	add_child(music)
	voice = AudioStreamPlayer.new()
	voice.bus = "Voice"
	voice.finished.connect(_on_voice_finished)
	add_child(voice)
	betty = AudioStreamPlayer.new()
	betty.bus = "Voice"
	add_child(betty)
	radio_player = AudioStreamPlayer.new()
	radio_player.bus = "Voice"
	add_child(radio_player)


## Start the pilots' radio for a mission (GameData.pilots maps each profile to its voice).
func setup_radio(pilot_profiles: Dictionary) -> void:
	radio = PilotRadio.new(manifest, pilot_profiles)


## Feed the radio one sim event and, once per tick, its poll (see PilotRadio).
func radio_event(e: Dictionary, world: SimWorld) -> void:
	if radio:
		radio.on_event(e, world, world.time, int(round(world.time / SimWorld.TICK)))


func radio_poll(world: SimWorld) -> void:
	if radio == null:
		return
	radio.poll(world, world.time, int(round(world.time / SimWorld.TICK)))
	_radio_update()


func _radio_update() -> void:
	if radio == null:
		return
	if not _radio_line.is_empty() and radio.current.is_empty():
		radio_player.stop()  # a priority-0 line (eject, death) cut this one off
		_radio_line = {}
		_radio_parts = []
	# Polled, not driven by the player's finished signal (it did not fire reliably in play): when the
	# fragment has ended, play the next one, or close the line and start the next queued line.
	if radio_player.playing:
		return
	if not _radio_parts.is_empty():
		_radio_play_next()
		return
	if not _radio_line.is_empty():
		_radio_line = {}
		radio.finished()
		if not voice.playing:
			AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), -9.0)
	var e := radio.next()
	if e.is_empty():
		return
	_radio_line = e
	_radio_parts = (e["lines"] as Array).duplicate()
	_radio_play_next()


func _radio_play_next() -> void:
	while not _radio_parts.is_empty():
		var part: Array = _radio_parts.pop_front()
		var s := _stream(String(part[1]))
		if s == null:
			continue
		if s is AudioStreamOggVorbis:
			(s as AudioStreamOggVorbis).loop = false
		radio_player.stream = s
		radio_player.play()
		AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), -18.0)
		if _radio_parts.is_empty():  # the message itself (a callsign goes first)
			radio_line.emit(_radio_line["unit"], String(part[0]))
		return


func _stream(path: String) -> AudioStream:
	if path.is_empty():
		return null
	if not _cache.has(path):
		_cache[path] = load(path) if ResourceLoader.exists(path) else null
	return _cache[path]


## Positional one-shot. Identical sounds within 60 ms are merged (volleys).
func play_at(path: String, at: Vector3, volume_db: float = 0.0) -> void:
	var s := _stream(path)
	if s == null:
		return
	var now := Time.get_ticks_msec()
	if now - int(_recent.get(path, -1000)) < 60:
		return
	_recent[path] = now
	var p := _pool[_next]
	_next = (_next + 1) % POOL
	p.stream = s
	p.volume_db = volume_db
	p.global_position = at
	p.play()


func sfx(key: String, at: Vector3, volume_db: float = 0.0) -> void:
	play_at(String(manifest.get("sfx", {}).get(key, "")), at, volume_db)


func weapon_fire(master_id: int, at: Vector3) -> void:
	play_at(String(manifest.get("weapons", {}).get(str(master_id), "")), at, -2.0)


func hit(form: String, damage: float, at: Vector3) -> void:
	var key := "laser_hit"
	if form == "MissileWeapon":
		key = "missile_hit"
	elif form != "EnergyWeapon":
		key = "heavy_hit" if damage >= 8.0 else "ballistic_hit"
	sfx(key, at, -3.0)


func say(vo_name: String) -> void:
	var path := String(manifest.get("vo", {}).get(vo_name, ""))
	if path.is_empty():
		return
	if voice.playing:
		_voice_queue.append(path)
	else:
		_play_voice(path)


func say_later(vo_name: String, delay: float, now: float) -> void:
	_scheduled.append([now + delay, vo_name])


func announce(key: String) -> void:
	var s := _stream(String(manifest.get("betty", {}).get(key, "")))
	if s:
		betty.stream = s
		betty.play()


func _play_voice(path: String) -> void:
	voice.stream = _stream(path)
	voice.play()
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), -18.0)


func _on_voice_finished() -> void:
	if not _voice_queue.is_empty():
		_play_voice(_voice_queue.pop_front())
	elif not radio_player.playing:
		AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), -9.0)


## Music selection, after mc2_01.abl: start tune once, then ambient; combat while
## the player is fighting; win/lose tunes at the end.
static func choose_tune(result: int, in_combat: bool, start_done: bool) -> int:
	if result == SimObjectives.Result.WON:
		return TUNE_WON
	if result == SimObjectives.Result.LOST:
		return TUNE_LOST
	if not start_done:
		return TUNE_START
	return TUNE_COMBAT if in_combat else TUNE_AMBIENT


## Play a tune by its sound ID (the mission script's playDigitalMusic). Win, lose and
## the start tune play once; the rest loop.
func play_tune(tune: int) -> void:
	if tune == current_tune and music.playing:
		return
	var s := _stream(String(manifest.get("music", {}).get(str(tune), "")))
	if s == null:
		return
	if s is AudioStreamOggVorbis:
		(s as AudioStreamOggVorbis).loop = not (tune in [TUNE_START, TUNE_LOST, TUNE_WON])
	current_tune = tune
	music.stream = s
	music.play()


func update_music(result: int, now: float) -> void:
	var tune := choose_tune(result, now - last_combat_time < COMBAT_HOLD, start_tune_done)
	if tune == current_tune and (music.playing or tune in [TUNE_WON, TUNE_LOST]):
		return
	if tune == TUNE_START and current_tune == TUNE_START and not music.playing:
		start_tune_done = true
		tune = choose_tune(result, now - last_combat_time < COMBAT_HOLD, true)
	var s := _stream(String(manifest.get("music", {}).get(str(tune), "")))
	if s == null:
		return
	if s is AudioStreamOggVorbis:
		(s as AudioStreamOggVorbis).loop = tune in [TUNE_AMBIENT, TUNE_COMBAT, 18, 19, 24]
	current_tune = tune
	music.stream = s
	music.play()


func tick(now: float) -> void:
	var due := []
	for s in _scheduled:
		if now >= s[0]:
			due.append(s)
	for s in due:
		_scheduled.erase(s)
		say(s[1])
