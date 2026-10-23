class_name BriefingMap
extends Control
## The briefing's tactical map, in the HUD style: the mission colour map, square and
## centred in a cyan frame with a faint grid, the drop zone (the original places it at the
## first player part, MissionBriefingScreen::setupDropZone) and a numbered marker per
## visible objective that has one (green primary, amber secondary). The selected objective
## glows; clicking a marker picks it.

signal picked(number: int)  # 1-based, as the objectives list numbers them

var brief: MissionBrief
var numbered: Array = []  # [[number, objective], ...] in list order (BriefingScreen sets it)
var selected := -1
var u := 11.4
var _tex: Texture2D


func _ready() -> void:
	if brief and brief.available:
		# The minimap's image: the colour map with the sea painted in (the raw colour map has none).
		var img := Minimap.build_image(SimMap.load_mission(brief.mission), brief.map_image, 512)
		_tex = ImageTexture.create_from_image(img)
	resized.connect(queue_redraw)
	mouse_filter = Control.MOUSE_FILTER_STOP


func map_rect() -> Rect2:
	var side := minf(size.x, size.y)
	return Rect2((size - Vector2(side, side)) / 2.0, Vector2(side, side))


## World metres (x east, y north, origin at the map centre) to a point in this control.
func to_local_point(world_m: Vector2) -> Vector2:
	var r := map_rect()
	var half := maxf(brief.map_half_m, 1.0)
	return r.position + Vector2((world_m.x + half) / (2.0 * half), (half - world_m.y) / (2.0 * half)) * r.size


func marker_radius() -> float:
	return maxf(9.0, u * 1.15)


func set_selected(n: int) -> void:
	selected = n
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and brief:
		for e in numbered:
			if e[1]["marker"] != null and to_local_point(e[1]["marker"]).distance_to(event.position) <= marker_radius() * 1.3:
				picked.emit(int(e[0]))
				accept_event()
				return


func _draw() -> void:
	var r := map_rect()
	if _tex:
		draw_texture_rect(_tex, r, false)
	else:
		draw_rect(r, Color(0.06, 0.1, 0.13))
	# grid: eight squares a side
	for i in range(1, 8):
		var t := r.size.x * i / 8.0
		draw_line(r.position + Vector2(t, 0), r.position + Vector2(t, r.size.y), Color(UiStyle.HUD_EDGE, 0.12), 1.0)
		draw_line(r.position + Vector2(0, t), r.position + Vector2(r.size.x, t), Color(UiStyle.HUD_EDGE, 0.12), 1.0)
	draw_rect(r, UiStyle.HUD_EDGE_SOFT, false, 1.0)
	var arm := maxf(10.0, u * 2.0)
	for c in [[r.position, Vector2(1, 1)], [r.position + Vector2(r.size.x, 0), Vector2(-1, 1)],
			[r.position + Vector2(0, r.size.y), Vector2(1, -1)], [r.end, Vector2(-1, -1)]]:
		draw_line(c[0], c[0] + Vector2(arm * c[1].x, 0), UiStyle.HUD_EDGE, 2.0)
		draw_line(c[0], c[0] + Vector2(0, arm * c[1].y), UiStyle.HUD_EDGE, 2.0)
	if brief == null:
		return
	var font := UiStyle.font("display700")
	var fs := maxi(8, roundi(u * 1.05))
	if brief.drop_zone != null:
		var p := to_local_point(brief.drop_zone)
		var k := marker_radius() * 0.9
		var dz := PackedVector2Array([p + Vector2(0, -k), p + Vector2(k, 0), p + Vector2(0, k), p + Vector2(-k, 0)])
		draw_colored_polygon(dz, Color(UiStyle.HUD_EDGE, 0.35))
		dz.append(dz[0])
		draw_polyline(dz, UiStyle.HUD_EDGE, 2.0, true)
		var t := "DZ"
		var ts := font.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
		draw_string(font, p + Vector2(k + 3.0, ts.y * 0.35), t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, UiStyle.HUD_EDGE)
	for e in numbered:
		var o: Dictionary = e[1]
		if o["marker"] == null:
			continue
		var p := to_local_point(o["marker"])
		var col: Color = UiStyle.HUD_OK if o["primary"] else UiStyle.HUD_WARN
		var rad := marker_radius()
		if int(e[0]) == selected:
			draw_circle(p, rad * 1.7, Color(col, 0.18))
			draw_arc(p, rad * 1.45, 0.0, TAU, 40, Color(UiStyle.HUD_INK, 0.9), 1.5, true)
		draw_circle(p, rad, Color(0.02, 0.06, 0.09, 0.8))
		draw_arc(p, rad, 0.0, TAU, 32, col, 2.0, true)
		var label := str(e[0])
		var sz := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
		draw_string(font, p + Vector2(-sz.x / 2.0, font.get_ascent(fs) * 0.42), label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
