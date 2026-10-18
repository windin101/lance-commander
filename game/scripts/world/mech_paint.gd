class_name MechPaint
extends RefCounted
## Team paint schemes, as Mech3DAppearance::setPaintScheme (mech3d.cpp:1613).
## Pure red, green or blue mask pixels become the scheme colour scaled by
## 1 - (1 - v/256)^2; any other pixel keeps its painted colour.
## Missions pass (HighlightColor1, HighlightColor2, BaseColor) for (red, green, blue).

static var _cache := {}


## ARGB int from a mission FIT (may be negative) -> Color.
static func argb(value: int) -> Color:
	var v := value & 0xFFFFFFFF
	return Color8((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


static func shade(channel: int) -> float:
	var x := 1.0 - float(channel) / 256.0
	return 1.0 - x * x


static func recolor(mask: Image, red: Color, green: Color, blue: Color) -> Image:
	var img := mask.duplicate() as Image
	img.convert(Image.FORMAT_RGBA8)
	var data := img.get_data()
	for i in range(0, data.size(), 4):
		var r := data[i]
		var g := data[i + 1]
		var b := data[i + 2]
		var c: Color
		var k: float
		if g == 0 and b == 0:
			c = red
			k = shade(r)
		elif r == 0 and b == 0:
			c = green
			k = shade(g)
		elif r == 0 and g == 0:
			c = blue
			k = shade(b)
		else:
			continue
		# The original truncates to unsigned char.
		data[i] = int(c.r8 * k)
		data[i + 1] = int(c.g8 * k)
		data[i + 2] = int(c.b8 * k)
		data[i + 3] = 255
	return Image.create_from_data(img.get_width(), img.get_height(), img.has_mipmaps(), Image.FORMAT_RGBA8, data)


static func load_mask(model_name: String, folder: String = "mechs") -> Image:
	var bytes := FileAccess.get_file_as_bytes("res://assets/%s/%s_paint.bin" % [folder, model_name])
	var img := Image.new()
	if bytes.is_empty() or img.load_png_from_buffer(bytes) != OK:
		return null
	return img


## Recolour every mesh under root with one material using the painted texture.
static func apply(root: Node, model_name: String, red: Color, green: Color, blue: Color, folder: String = "mechs") -> void:
	var key := "%s/%s|%s|%s|%s" % [folder, model_name, red.to_html(), green.to_html(), blue.to_html()]
	var mat: StandardMaterial3D = _cache.get(key)
	if mat == null:
		var mask := load_mask(model_name, folder)
		if mask == null:
			return
		var painted := recolor(mask, red, green, blue)
		painted.generate_mipmaps()
		mat = StandardMaterial3D.new()
		mat.albedo_texture = ImageTexture.create_from_image(painted)
		mat.metallic = 0.35
		mat.roughness = 0.55
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		_cache[key] = mat
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_override = mat
