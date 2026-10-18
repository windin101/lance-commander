extends Control
## Opening cinematic (CINEMA1 from the user's retail disc, if converted), then
## the mission. Esc / Space / click skips. Without the video it goes straight on.

const NEXT := "res://scenes/mission_view.tscn"

var player: VideoStreamPlayer


func _ready() -> void:
	var videos: Dictionary = {}
	if FileAccess.file_exists("res://data/videos.json"):
		videos = JSON.parse_string(FileAccess.get_file_as_string("res://data/videos.json"))
	var path := String(videos.get("cinema1", ""))
	if path.is_empty() or not ResourceLoader.exists(path) or OS.get_cmdline_user_args().has("--skip-intro"):
		_next.call_deferred()
		return
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	player = VideoStreamPlayer.new()
	player.set_anchors_preset(Control.PRESET_FULL_RECT)
	player.expand = true
	player.stream = load(path)
	player.finished.connect(_next)
	add_child(player)
	var hint := Label.new()
	hint.text = "Esc to skip"
	hint.modulate = Color(1, 1, 1, 0.5)
	hint.position = Vector2(16, 12)
	add_child(hint)
	player.play()


func _unhandled_input(event: InputEvent) -> void:
	if (event is InputEventKey and event.pressed and event.keycode in [KEY_ESCAPE, KEY_SPACE, KEY_ENTER]) \
			or (event is InputEventMouseButton and event.pressed):
		_next()


func _next() -> void:
	if is_inside_tree():
		get_tree().change_scene_to_file(NEXT)
