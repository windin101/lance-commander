class_name BriefingMap
extends Control
## The briefing's tactical map: the mission colour map, square and centred, with a
## numbered marker per visible objective that has one (green primary, amber secondary).

var brief: MissionBrief
var _tex: Texture2D


func _ready() -> void:
	if brief and brief.available:
		# The minimap's image: the colour map with the sea painted in (the raw colour map has none).
		var img := Minimap.build_image(SimMap.load_mission(brief.mission), brief.map_image, 512)
		_tex = ImageTexture.create_from_image(img)
	resized.connect(queue_redraw)


func map_rect() -> Rect2:
	var side := minf(size.x, size.y)
	return Rect2((size - Vector2(side, side)) / 2.0, Vector2(side, side))


## World metres (x east, y north, origin at the map centre) to a point in this control.
func to_local_point(world_m: Vector2) -> Vector2:
	var r := map_rect()
	var half := maxf(brief.map_half_m, 1.0)
	return r.position + Vector2((world_m.x + half) / (2.0 * half), (half - world_m.y) / (2.0 * half)) * r.size


func _draw() -> void:
	var r := map_rect()
	if _tex:
		draw_texture_rect(_tex, r, false)
	else:
		draw_rect(r, Color(0.08, 0.12, 0.1))
	draw_rect(r, UiStyle.PANEL_EDGE, false, 1.0)
	if brief == null:
		return
	var font := get_theme_default_font()
	var n := 0
	for o in brief.visible_objectives():
		n += 1
		if o["marker"] == null:
			continue
		var p := to_local_point(o["marker"])
		var col: Color = UiStyle.ACCENT if o["primary"] else UiStyle.WARN
		draw_circle(p, 13.0, Color(0, 0, 0, 0.55))
		draw_arc(p, 13.0, 0.0, TAU, 32, col, 2.0, true)
		var label := str(n)
		var sz := font.get_string_size(label, HORIZONTAL_ALIGNMENT_CENTER, -1, 14)
		draw_string(font, p + Vector2(-sz.x / 2.0, 5.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, col)
