class_name PaintPanel
extends VBoxContainer
## The player's paint scheme picker, in the HUD style: presets, a pattern (plain, woodland, snow or urban
## camouflage) and the three colours (base, trim = highlight 1, accent = highlight 2), each from a row of swatches
## or a custom colour. Every change is saved (PaintScheme.set_player, user://settings.cfg [paint]) and emitted as
## `changed`, so the host can repaint its preview: the Mech Bay's 'Mech, or the player's units in a mission.

signal changed(scheme: Dictionary)

const PRESETS := [
	{"name": "Default", "base": "#9a9a9a", "hl1": "#d02e11", "hl2": "#4a4a4c", "pattern": "plain"},
	{"name": "Woodland", "base": "#5a6240", "hl1": "#c8a050", "hl2": "#3a3a2c", "pattern": "woodland"},
	{"name": "Snow", "base": "#d0d4d8", "hl1": "#c02818", "hl2": "#50555a", "pattern": "snow"},
	{"name": "Urban", "base": "#6c7076", "hl1": "#e0b030", "hl2": "#2c3036", "pattern": "urban"},
	{"name": "Desert", "base": "#b39b70", "hl1": "#7a3a1c", "hl2": "#3c3a34", "pattern": "plain"},
	{"name": "Midnight", "base": "#2b3038", "hl1": "#3aa0d8", "hl2": "#16181c", "pattern": "plain"},
]
const SWATCHES := ["#9a9a9a", "#d8dadc", "#5c5f63", "#2b3038", "#d02e11", "#9e0500", "#e07a1a", "#e0b030",
	"#b8925a", "#5a6240", "#3a5a2a", "#003412", "#2f4f8f", "#002882", "#3aa0d8", "#6b3a1e"]
const LABELS := {"base": "Base", "hl1": "Trim", "hl2": "Accent"}

var kit: BayKit
var scheme := {}
var _pattern_buttons := {}
var _swatch_rows := {}
var _pickers := {}


func _init(k: BayKit) -> void:
	kit = k
	add_theme_constant_override("separation", kit.px(0.7))
	scheme = PaintScheme.player()
	add_child(kit.label("Presets", "display600", 0.85, UiStyle.HUD_DIM, true, 0.14))
	var pre := HFlowContainer.new()
	pre.add_theme_constant_override("h_separation", kit.px(0.4))
	pre.add_theme_constant_override("v_separation", kit.px(0.4))
	for p in PRESETS:
		pre.add_child(kit.button(String(p["name"]), func(): _apply_preset(p)))
	add_child(pre)
	add_child(kit.label("Pattern", "display600", 0.85, UiStyle.HUD_DIM, true, 0.14))
	var pat := HBoxContainer.new()
	pat.add_theme_constant_override("separation", kit.px(0.4))
	for name in PaintScheme.PLAYER_PATTERNS:
		var b := kit.button(String(name), func(): _set_value("pattern", name))
		b.toggle_mode = true
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_pattern_buttons[name] = b
		pat.add_child(b)
	add_child(pat)
	for key in ["base", "hl1", "hl2"]:
		add_child(kit.label(LABELS[key], "display600", 0.85, UiStyle.HUD_DIM, true, 0.14))
		var row := HFlowContainer.new()
		row.add_theme_constant_override("h_separation", kit.px(0.3))
		row.add_theme_constant_override("v_separation", kit.px(0.3))
		for hex in SWATCHES:
			row.add_child(_swatch(key, Color(hex)))
		var cp := ColorPickerButton.new()
		cp.custom_minimum_size = Vector2(kit.em(2.4), kit.em(1.6))
		cp.edit_alpha = false
		cp.tooltip_text = "Custom colour"
		cp.focus_mode = Control.FOCUS_NONE
		cp.color_changed.connect(func(c: Color): _set_value(key, "#" + c.to_html(false)))
		_pickers[key] = cp
		row.add_child(cp)
		_swatch_rows[key] = row
		add_child(row)
	_sync()


func _swatch(key: String, c: Color) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(kit.em(1.6), kit.em(1.6))
	b.focus_mode = Control.FOCUS_NONE
	b.tooltip_text = "#" + c.to_html(false)
	for state in ["normal", "hover", "pressed"]:
		var s := StyleBoxFlat.new()
		s.bg_color = c
		s.border_color = UiStyle.HUD_EDGE if state != "normal" else Color(UiStyle.HUD_EDGE_SOFT, 0.6)
		s.set_border_width_all(1 if state == "normal" else 2)
		b.add_theme_stylebox_override(state, s)
	b.pressed.connect(func(): _set_value(key, "#" + c.to_html(false)))
	return b


func _apply_preset(p: Dictionary) -> void:
	for k in ["base", "hl1", "hl2", "pattern"]:
		scheme[k] = p[k]
	_commit()


func _set_value(key: String, value) -> void:
	scheme[key] = value
	_commit()


func _commit() -> void:
	PaintScheme.set_player(Color(String(scheme["base"])), Color(String(scheme["hl1"])), Color(String(scheme["hl2"])),
		String(scheme.get("pattern", "plain")))
	scheme = PaintScheme.player()
	_sync()
	changed.emit(scheme)


func _sync() -> void:
	for name in _pattern_buttons:
		(_pattern_buttons[name] as Button).set_pressed_no_signal(String(scheme.get("pattern", "plain")) == name)
	for key in _pickers:
		(_pickers[key] as ColorPickerButton).color = Color(String(scheme[key]))
