class_name CommandPanel
extends PanelContainer
## Command panel (bottom centre; the original's command palette plus its support tab, in
## the approved mock-up's layout): icon buttons for run, jump, guard, stop, fire from
## position, hold and alpha strike with their hotkeys, then the support powers as cost tiles
## (unaffordable ones greyed) and the Resource Points total. Emits the player's choice;
## MissionHud turns it into orders.

signal command(kind: String)
signal support(kind: String)

const WIDTH_EM := 35.3
## [id, title, hotkey, help]: the mock-up's (and the original's) letters. CommandInput binds
## H (hold) and A (alpha strike) today; R, J, G, S and F (fire from position) are not bound yet.
const COMMANDS := [
	["run", "Run", "R", "Selected units run to the next point you right-click."],
	["jump", "Jump", "J", "Selected 'Mechs with jump jets jump to the next point you right-click."],
	["guard", "Guard", "G", "Selected units hold this area and engage anything that enters it."],
	["stop", "Stop", "S", "Selected units stop where they are."],
	["fire_from_position", "Fire from position", "F", "Selected units fire on the next target without moving."],
	["hold", "Hold", "H", "Selected units hold position and fire only when fired on."],
	["alpha_strike", "Alpha strike", "A", "Fire every weapon regardless of heat. Toggle."],
]
const SUPPORT_HELP := {
	"air_strike": "Call an air strike on a point. It lands seven seconds later.",
	"sensor_probe": "Drop a sensor probe: reveals enemies around it for two minutes.",
	"repair_truck": "Deliver a repair truck. Select it and right-click a damaged 'Mech.",
	"salvage_craft": "Send a salvage craft to a disabled 'Mech to recover it.",
}

var kit: HudKit
var icons := {}  # command id -> IconButton
var tiles := {}  # support power -> SupportTile
var rp_label: Label
var hover_help: Callable  # (key) -> void


func _init(hud_kit: HudKit, with_support: bool) -> void:
	kit = hud_kit
	custom_minimum_size.x = kit.em(WIDTH_EM)
	add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	mouse_filter = Control.MOUSE_FILTER_STOP
	var p := kit.panel("Command", "right-click to move or attack")
	var v: VBoxContainer = p["body"]
	p["panel"].remove_child(v)
	p["panel"].free()
	add_child(v)
	var im := kit.margin(0.8, 0.7, 0.8, 0.4)
	v.add_child(im)
	var row := kit.hbox(0.45)
	im.add_child(row)
	var side := (WIDTH_EM - 1.6 - 6 * 0.45) / 7.0
	for c in COMMANDS:
		var b := IconButton.new()
		b.id = c[0]
		b.key = c[2]
		b.u = kit.u
		b.hot = c[0] == "alpha_strike"
		b.custom_minimum_size = Vector2(kit.em(side), kit.em(side))
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(func(): command.emit(c[0]))
		b.mouse_entered.connect(func(): _hover(c[0]))
		b.mouse_exited.connect(func(): _hover(""))
		row.add_child(b)
		icons[c[0]] = b
	if not with_support:
		v.add_child(kit.margin(0, 0, 0, 0.4))
		return
	var sm := kit.margin(0.8, 0.4, 0.8, 0.8)
	v.add_child(sm)
	var srow := kit.hbox(0.45)
	sm.add_child(srow)
	for kind in SimSupport.ORDER:
		var t := SupportTile.new(kit, SimSupport.LABELS[kind], SimSupport.COSTS[kind])
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		t.clicked.connect(func(): support.emit(kind))
		t.mouse_entered.connect(func(): _hover(kind))
		t.mouse_exited.connect(func(): _hover(""))
		srow.add_child(t)
		tiles[kind] = t
	var rp := PanelContainer.new()
	var rs := StyleBoxFlat.new()
	rs.bg_color = Color(UiStyle.HUD_EDGE, 0.10)
	rs.border_color = UiStyle.HUD_EDGE
	rs.set_border_width_all(1)
	rs.set_content_margin_all(kit.em(0.3))
	rp.add_theme_stylebox_override("panel", rs)
	rp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rp.size_flags_stretch_ratio = 1.25
	rp.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var rv := VBoxContainer.new()
	rv.add_theme_constant_override("separation", 0)
	rv.alignment = BoxContainer.ALIGNMENT_CENTER
	rp.add_child(rv)
	var cap := kit.label("RESOURCE POINTS", "display500", 0.8, UiStyle.HUD_DIM, false, 0.14)
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rv.add_child(cap)
	rp_label = kit.label("0", "mono", 1.5, UiStyle.HUD_EDGE)
	rp_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rv.add_child(rp_label)
	srow.add_child(rp)


func _hover(key: String) -> void:
	if hover_help.is_valid():
		hover_help.call(key)


## Title and description for the rollover help line, or [] for an unknown key.
static func help_for(key: String) -> Array:
	for c in COMMANDS:
		if c[0] == key:
			return [c[1], c[3]]
	if SUPPORT_HELP.has(key):
		return ["%s  %s RP" % [SimSupport.LABELS[key], thousands(SimSupport.COSTS[key])], SUPPORT_HELP[key]]
	return []


static func thousands(n: int) -> String:
	var s := str(absi(n))
	var out := ""
	while s.length() > 3:
		out = "," + s.right(3) + out
		s = s.left(s.length() - 3)
	return ("-" if n < 0 else "") + s + out


## Light the armed command, the alpha-strike state and the support tiles.
func update_state(mode: String, alpha_on: bool, sup: SimSupport, armed_power: String) -> void:
	for id in icons:
		var b: IconButton = icons[id]
		b.on = (id == mode) or (id == "alpha_strike" and alpha_on)
	if sup == null:
		return
	rp_label.text = thousands(sup.rp)
	for kind in tiles:
		var t: SupportTile = tiles[kind]
		t.disabled = not sup.can_call(kind)
		t.pressed = armed_power == kind


## A square command button with a vector icon and its hotkey in the corner.
class IconButton:
	extends Control
	signal pressed
	var id := ""
	var key := ""
	var u := 11.4
	var hot := false
	var on := false:
		set(v):
			if v != on:
				on = v
				queue_redraw()
	var _hover := false

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP
		mouse_entered.connect(func(): _hover = true; queue_redraw())
		mouse_exited.connect(func(): _hover = false; queue_redraw())

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			pressed.emit()
			accept_event()

	func _draw() -> void:
		var side := minf(size.x, size.y)
		var r := Rect2((size - Vector2(side, side)) / 2.0, Vector2(side, side))
		var fill := Color(UiStyle.HUD_EDGE, 0.22 if on else (0.14 if _hover else 0.06))
		var edge := UiStyle.HUD_EDGE if (on or _hover) else UiStyle.HUD_EDGE_SOFT
		if hot:
			edge = UiStyle.HUD_HOT
			if on:
				fill = Color(UiStyle.HUD_HOT, 0.25)
		if on:
			draw_rect(r.grow(u * 0.25), Color(UiStyle.HUD_HOT if hot else UiStyle.HUD_EDGE, 0.12))
		draw_rect(r, fill)
		draw_rect(r, edge, false, 1.0)
		var ic := r.size.x * 0.62
		HudKit.draw_icon(self, id, Rect2(r.get_center() - Vector2(ic, ic) / 2.0, Vector2(ic, ic)),
			UiStyle.HUD_HOT if hot else UiStyle.HUD_INK)
		if not key.is_empty():
			var f := UiStyle.font("mono")
			var fs := maxi(6, roundi(u * 0.75))
			var ks := f.get_string_size(key, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
			draw_string(f, Vector2(r.end.x - ks.x - u * 0.2, r.end.y - u * 0.1 - f.get_descent(fs)), key,
				HORIZONTAL_ALIGNMENT_LEFT, -1, fs, UiStyle.HUD_DIM)


## A support power tile: name and cost; greyed when it can't be afforded.
class SupportTile:
	extends PanelContainer
	signal clicked
	var disabled := false:
		set(v):
			if v != disabled:
				disabled = v
				modulate.a = 0.45 if v else 1.0
	var pressed := false:
		set(v):
			if v != pressed:
				pressed = v
				_style()
	var _kit: HudKit

	func _init(kit: HudKit, title: String, cost: int) -> void:
		_kit = kit
		mouse_filter = Control.MOUSE_FILTER_STOP
		_style()
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", roundi(kit.em(0.25)))
		v.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(v)
		var t := kit.label(title, "display500", 0.85, UiStyle.HUD_INK, true, 0.08)
		t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		t.custom_minimum_size.x = kit.em(4.5)
		v.add_child(t)
		v.add_child(kit.label(CommandPanel.thousands(cost), "mono", 0.9, UiStyle.HUD_DIM))

	func _style() -> void:
		var s := StyleBoxFlat.new()
		s.bg_color = Color(UiStyle.HUD_EDGE, 0.22) if pressed else Color(1, 1, 1, 0.03)
		s.border_color = UiStyle.HUD_EDGE if pressed else UiStyle.HUD_EDGE_SOFT
		s.set_border_width_all(1)
		s.content_margin_left = _kit.em(0.4)
		s.content_margin_right = _kit.em(0.4)
		s.content_margin_top = _kit.em(0.35)
		s.content_margin_bottom = _kit.em(0.35)
		add_theme_stylebox_override("panel", s)

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			if not disabled:
				clicked.emit()
			accept_event()
