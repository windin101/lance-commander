class_name UnitCard
extends Control
## Force-bar card for one player unit: name, damage diagram, heat and status.
## Left-click selects the unit (shift adds).

signal picked(unit: SimUnit, add: bool)

var unit: SimUnit
var selected := false


func _init(u: SimUnit) -> void:
	unit = u
	custom_minimum_size = Vector2(176, 140)
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = u.name


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		picked.emit(unit, event.shift_pressed)
		accept_event()


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	var font := get_theme_default_font()
	var bg := Color(0.05, 0.07, 0.08, 0.82)
	draw_rect(Rect2(Vector2.ZERO, size), bg)
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.4, 1.0, 0.5) if selected else Color(0.3, 0.35, 0.38), false, 2.0 if selected else 1.0)
	draw_string(font, Vector2(8, 18), unit.name, HORIZONTAL_ALIGNMENT_LEFT, size.x - 16, 16, Color(0.9, 0.95, 0.9))
	var doll := Rect2(Vector2(8, 28), Vector2(72, 94))
	for c in PaperDoll.cells(unit, doll):
		draw_rect(c[0], c[1])
		draw_rect(c[0], Color(0, 0, 0, 0.6), false, 1.0)
	var x := 90.0
	var status: String = ["OK", "SHUTDOWN", "DISABLED", "DESTROYED"][unit.status]
	if unit is SimMech and unit.fallen and not unit.is_disabled():
		status = "FALLEN"
	if unit.powered_down and not unit.is_disabled():
		status = "POWERED DOWN"
	var status_col := Color(0.6, 1.0, 0.6) if status == "OK" else Color(1.0, 0.55, 0.3)
	draw_string(font, Vector2(x, 42), status, HORIZONTAL_ALIGNMENT_LEFT, size.x - x - 4, 13, status_col)
	draw_string(font, Vector2(x, 60), "ARMOUR", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.7, 0.75, 0.75))
	_bar(Rect2(x, 64, size.x - x - 8, 7), PaperDoll.armor_fraction(unit), Color(0.35, 0.8, 0.4))
	if unit.uses_heat:
		draw_string(font, Vector2(x, 86), "HEAT", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.7, 0.75, 0.75))
		var lvl := float(unit.heat_level()) / 30.0
		_bar(Rect2(x, 90, size.x - x - 8, 7), lvl, Color(1.0, 0.6 - lvl * 0.5, 0.1))
	if unit.ignore_heat_discipline:
		draw_string(font, Vector2(x, 112), "ALPHA STRIKE", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1.0, 0.35, 0.3))
	if unit.current_target and not unit.current_target.is_disabled():
		draw_string(font, Vector2(8, 134), "> " + unit.current_target.name, HORIZONTAL_ALIGNMENT_LEFT, size.x - 16, 12, Color(1.0, 0.75, 0.6))


func _bar(r: Rect2, frac: float, col: Color) -> void:
	draw_rect(r, Color(0.15, 0.15, 0.15))
	draw_rect(Rect2(r.position, Vector2(r.size.x * clampf(frac, 0.0, 1.0), r.size.y)), col)
