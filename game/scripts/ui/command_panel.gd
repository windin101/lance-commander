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
## [id, title, hotkey, help]: the original's keys (missiongui.cpp:198-300; CommandInput binds
## them): Space, J, G and C arm their mode while held, Backspace stops, H toggles hold.
## A is this port's alpha strike (the original's A fires energy weapons only).
const COMMANDS := [
	["run", "Run", "SPC", "Selected units run on their next order. Hold Space, or toggle."],
	["jump", "Jump", "J", "Selected 'Mechs with jump jets jump to the next point you right-click (128 m)."],
	["guard", "Guard", "G", "Right-click a point or a unit: selected units guard it and engage anything that comes near."],
	["stop", "Stop", "BKSP", "Selected units drop their orders and stop where they are."],
	["fire_from_position", "Fire from position", "C", "Selected units fire on the next target you right-click without moving."],
	["hold", "Hold", "H", "Selected units hold position: they fire but move only when ordered to. Toggle."],
	["alpha_strike", "Alpha strike", "A", "Fire every weapon regardless of heat. Toggle."],
	# the original's range buttons (ControlGui SHORT/MED/LONG_RANGE, controlGui.h:181-184) and keys
	["short", "Short range", "S", "Attack from short range (30 m). Hold S and right-click, or toggle; off again for the best range."],
	["medium", "Medium range", "M", "Attack from medium range (45 m). Hold M and right-click, or toggle."],
	["long", "Long range", "L", "Attack from long range (60 m). Hold L and right-click, or toggle."],
	["force_fire", "Force fire", "F", "Fire on whatever you right-click next: the ground, a building or your own unit."],
	["lay_mines", "Lay mines", "", "Selected minelayers lay a mine in every cell they drive through on their next moves. Toggle."],
	["suppress", "Suppression fire", "", "Selected artillery pieces keep shelling the ground point you right-click. Toggle off to stop."],
]
## Waypoints have no button: hold Ctrl while giving orders to queue them (the original's
## waypoint key, missiongui.cpp:842).
const SUPPORT_HELP := {
	"air_strike": "Call an air strike on a point. It lands seven seconds later.",
	"sensor_probe": "Drop a sensor probe: reveals enemies around it for two minutes.",
	"artillery_piece": "Deliver a Long Tom artillery piece. It shells enemies in reach, even out of its own sight when your units see them.",
	"repair_truck": "Deliver a repair truck. Select it and right-click a damaged 'Mech.",
	"scout_copter": "Deliver a scout copter: a fast, unarmed flier that sees over anything. It can't capture.",
	"minelayer": "Deliver a minelayer. Select it, press Lay mines and right-click: it lays mines along the way.",
	"salvage_craft": "Send a salvage craft to a disabled 'Mech to recover it.",
}

## Tile titles: short, so six tiles fit the row (the original's tab shows icons); the rollover
## help gives the full name and cost.
const TILE_LABELS := {"air_strike": "Air strike", "artillery_piece": "Artillery", "sensor_probe": "Probe",
	"repair_truck": "Repair", "scout_copter": "Scout", "minelayer": "Mines", "salvage_craft": "Salvage"}

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
	var row := kit.hbox(0.3)
	im.add_child(row)
	var side := (WIDTH_EM - 1.6 - (COMMANDS.size() - 1) * 0.3) / COMMANDS.size()
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
		var t := SupportTile.new(kit, TILE_LABELS.get(kind, SimSupport.LABELS[kind]), SimSupport.COSTS[kind])
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
	rp.size_flags_stretch_ratio = 1.0
	rp.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var rv := VBoxContainer.new()
	rv.add_theme_constant_override("separation", 0)
	rv.alignment = BoxContainer.ALIGNMENT_CENTER
	rp.add_child(rv)
	var cap := kit.label("RESOURCE POINTS", "display500", 0.8, UiStyle.HUD_DIM, false, 0.14)
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.autowrap_mode = TextServer.AUTOWRAP_WORD  # two lines, so six tiles fit beside it
	cap.custom_minimum_size.x = kit.em(4.6)
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


## Light the armed modes and unit settings (on: command id -> bool), grey Jump when the
## selection has no jump jets (controlGui.cpp:1163-1166), and update the support tiles.
func update_state(on: Dictionary, sup: SimSupport, armed_power: String, can_jump := true) -> void:
	for id in icons:
		var b: IconButton = icons[id]
		b.on = on.get(id, false)
		b.disabled = (id == "jump" and not can_jump) or (id == "lay_mines" and not on.get("can_lay_mines", false)) \
			or (id == "suppress" and not on.get("can_suppress", false))
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
	var disabled := false:
		set(v):
			if v != disabled:
				disabled = v
				modulate.a = 0.4 if v else 1.0
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
		v.add_theme_constant_override("separation", roundi(kit.em(0.15)))
		v.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(v)
		var t := kit.label(title, "display500", 0.8, UiStyle.HUD_INK, true, 0.06)
		t.autowrap_mode = TextServer.AUTOWRAP_WORD  # break between words only, never "STRIK E"
		var f := t.get_theme_font("font")
		var fs := t.get_theme_font_size("font_size")
		var widest := 0.0
		for w in title.to_upper().split(" ", false):
			widest = maxf(widest, f.get_string_size(w, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x)
		t.custom_minimum_size.x = maxf(kit.em(2.9), ceilf(widest))  # six tiles share the row (support tab, controlGui.cpp:80-115)
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
