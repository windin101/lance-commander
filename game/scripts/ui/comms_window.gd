class_name CommsWindow
extends PanelContainer
## The in-mission comms panel (top left; the original's pilot video window, restyled to the
## approved mock-up): portrait, speaker and a subtitle line, shown only while someone is
## talking. Plays a talking-head clip (retail videos, when present) in the portrait slot,
## shows a pilot line (say) for a few seconds, or a plain "incoming transmission" while a
## mission voice-over plays (set_voice). Emits `finished` when a clip ends. The speaker's
## lance card blinks yellow while speaker_unit is set (MissionHud).

signal finished

const WIDTH_EM := 25.9
const BLINK_PERIOD := 0.25

var kit: HudKit
var player: VideoStreamPlayer
var portrait: TextureRect
var slot: Control
var ring: Control  # the blinking "speaking" outline over the portrait
var caption: Label  # the speaker line
var subtitle: Label
var speaker_unit: SimUnit = null
var _line_until := -1.0  # ticks (s) when a say() line ends
var _voice := false


func _ready() -> void:
	if kit == null:
		kit = HudKit.new(UiStyle.hud_unit(1080.0))
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u, Vector4(kit.em(0.7), kit.em(0.7), kit.em(0.7), kit.em(0.7))))
	custom_minimum_size.x = kit.em(WIDTH_EM)
	var row := kit.hbox(0.8)
	add_child(row)
	slot = Control.new()
	slot.custom_minimum_size = Vector2(kit.em(5.4), kit.em(5.4) * 46.0 / 33.0)
	slot.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(slot)
	portrait = TextureRect.new()
	portrait.texture = PilotPortraits.placeholder()
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	portrait.set_anchors_preset(Control.PRESET_FULL_RECT)
	portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(portrait)
	player = VideoStreamPlayer.new()
	player.expand = true
	player.bus = "Voice"
	player.visible = false
	player.set_anchors_preset(Control.PRESET_FULL_RECT)
	player.finished.connect(_on_finished)
	slot.add_child(player)
	ring = Control.new()
	ring.set_anchors_preset(Control.PRESET_FULL_RECT)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ring.draw.connect(_draw_ring)
	slot.add_child(ring)
	var text := kit.vbox(0.2)
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(text)
	caption = kit.label("TAC OFFICER", "display500", 0.95, UiStyle.HUD_EDGE, true, 0.08)
	text.add_child(caption)
	subtitle = kit.para("", WIDTH_EM - 1.4 - 5.4 - 0.8, "body400", 1.1, UiStyle.HUD_INK)
	text.add_child(subtitle)


## Play a video by res path; returns false (and emits nothing) if it isn't available.
func play(path: String, title: String = "TAC OFFICER") -> bool:
	if path.is_empty() or not ResourceLoader.exists(path):
		return false
	player.stream = load(path)
	caption.text = title
	subtitle.text = ""
	player.visible = true
	portrait.visible = false
	slot.custom_minimum_size.x = slot.custom_minimum_size.y * 4.0 / 3.0  # the clips are 4:3
	visible = true
	player.play()
	return true


## Show a pilot (or anyone) talking: speaker, subtitle, for seconds (default from the
## text length). unit, when given, gets the blinking outline on its lance card.
func say(speaker: String, text: String, unit: SimUnit = null, seconds := -1.0, profile := "") -> void:
	caption.text = speaker
	subtitle.text = text
	speaker_unit = unit
	portrait.texture = PilotPortraits.texture_for(profile if not profile.is_empty() else (unit.pilot_profile if unit else ""))
	if seconds < 0.0:
		seconds = 2.5 + 0.06 * text.length()
	_line_until = Time.get_ticks_msec() / 1000.0 + seconds
	visible = true


## A mission voice-over is playing (AudioDirector.voice): keep the panel up while it does.
func set_voice(active: bool) -> void:
	_voice = active


func is_playing() -> bool:
	return visible and player.is_playing()


## Someone is talking: a clip, a say() line or a voice-over.
func talking() -> bool:
	return player.is_playing() or Time.get_ticks_msec() / 1000.0 < _line_until or _voice


func _process(_delta: float) -> void:
	var line := Time.get_ticks_msec() / 1000.0 < _line_until
	if player.is_playing() or line:
		visible = true
	elif _voice:
		if not visible:
			caption.text = "Command"
			subtitle.text = "Incoming transmission."
			speaker_unit = null
			portrait.texture = PilotPortraits.placeholder()
		visible = true
	elif visible:
		visible = false
		speaker_unit = null
	if visible:
		ring.queue_redraw()


func _draw_ring() -> void:
	if int(Time.get_ticks_msec() / (BLINK_PERIOD * 500.0)) % 2 == 0:
		ring.draw_rect(Rect2(Vector2.ONE, ring.size - Vector2(2, 2)), UiStyle.HUD_WARN, false, 2.0)


func _on_finished() -> void:
	player.visible = false
	portrait.visible = true
	slot.custom_minimum_size.x = kit.em(5.4)
	finished.emit()
