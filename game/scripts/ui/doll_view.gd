class_name DollView
extends Control
## A unit's damage diagram (the original's info-tab paper doll). With an index mask
## (PaperDoll.mask_for) it draws the mask through shaders/paper_doll.gdshader: each location
## filled at 35% of its PaperDoll colour with full-alpha borders. Without one it draws the
## PaperDoll rectangle layout the same way. rear shows the rear torso armour only.
## Used by the systems monitor (front and rear) and the lance cards (small, front).

const SHADER := preload("res://shaders/paper_doll.gdshader")
const FILL_ALPHA := 0.35

var unit: SimUnit
var rear := false
var mask: Dictionary = {}
var _mat: ShaderMaterial
var _colours := PackedColorArray()


func _init(u: SimUnit = null, rear_view := false) -> void:
	unit = u
	rear = rear_view
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST


func _ready() -> void:
	set_unit(unit)


func set_unit(u: SimUnit) -> void:
	unit = u
	mask = PaperDoll.mask_for(u.model) if u else {}
	_colours = PackedColorArray()
	if mask.is_empty():
		material = null
		_mat = null
	else:
		_mat = ShaderMaterial.new()
		_mat.shader = SHADER
		_mat.set_shader_parameter("count", 8 if u is SimMech else 5)
		_mat.set_shader_parameter("fill_alpha", FILL_ALPHA)
		material = _mat
	queue_redraw()


## True when drawing a generated mask rather than the rectangle fallback.
func has_mask() -> bool:
	return not mask.is_empty()


func _process(_delta: float) -> void:
	if unit == null or not is_visible_in_tree():
		return
	var c := PaperDoll.location_colours(unit, rear)
	if c != _colours:
		_colours = c
		if _mat:
			_mat.set_shader_parameter("colors", c)
		queue_redraw()


## The drawing rect: the mask's (or the layout's square) aspect, fitted and centred.
func doll_rect() -> Rect2:
	var aspect := 1.0
	if has_mask():
		var r: Rect2 = mask["region"]
		aspect = r.size.x / maxf(r.size.y, 1.0)
	var s := size
	var w := minf(s.x, s.y * aspect)
	var h := w / aspect
	return Rect2((s - Vector2(w, h)) / 2.0, Vector2(w, h))


func _draw() -> void:
	if unit == null:
		return
	var box := doll_rect()
	if has_mask():
		draw_texture_rect_region(mask["texture"], box, mask["region"])
		return
	var layout: Array = PaperDoll.MECH_LAYOUT if unit is SimMech else PaperDoll.VEHICLE_LAYOUT
	var cols := PaperDoll.location_colours(unit, rear)
	var stroke := maxf(1.0, size.y / 90.0)
	for i in layout.size():
		var c: Color = cols[i]
		if c.a <= 0.0:
			continue
		var r := Rect2(box.position + layout[i].position * box.size, layout[i].size * box.size).grow(-stroke * 0.5)
		draw_rect(r, Color(c, c.a * FILL_ALPHA))
		draw_rect(r, c, false, stroke)
