class_name CommsWindow
extends PanelContainer
## The in-mission comms window: plays a talking-head clip (retail videos,
## when present) with a caption. Emits `finished` when the clip ends.

signal finished

var player: VideoStreamPlayer
var caption: Label


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.03, 0.05, 0.06, 0.88)
	style.border_color = Color(0.35, 0.8, 0.5)
	style.set_border_width_all(2)
	style.set_content_margin_all(6)
	add_theme_stylebox_override("panel", style)
	var box := VBoxContainer.new()
	add_child(box)
	caption = Label.new()
	caption.text = "TAC OFFICER"
	caption.add_theme_font_size_override("font_size", 14)
	caption.add_theme_color_override("font_color", Color(0.5, 1.0, 0.6))
	box.add_child(caption)
	player = VideoStreamPlayer.new()
	player.custom_minimum_size = Vector2(320, 180)
	player.expand = true
	player.bus = "Voice"
	player.finished.connect(_on_finished)
	box.add_child(player)


## Play a video by res path; returns false (and emits nothing) if it isn't available.
func play(path: String, title: String = "TAC OFFICER") -> bool:
	if path.is_empty() or not ResourceLoader.exists(path):
		return false
	player.stream = load(path)
	caption.text = title
	visible = true
	player.play()
	return true


func is_playing() -> bool:
	return visible and player.is_playing()


func _on_finished() -> void:
	visible = false
	finished.emit()
