class_name PilotPortraits
extends RefCounted
## Pilot portrait lookup for the HUD (lance cards, comms). A generated face at
## assets/ui/portraits/<pilot profile>.png wins when it exists; until those are made every
## pilot gets the silhouette placeholder of the approved mock-up (head and shoulders on the
## dark portrait well, 33:46).

const DIR := "res://assets/ui/portraits"

static var _cache := {}
static var _placeholder: ImageTexture


## The portrait for a pilot profile (SimUnit.pilot_profile, e.g. "pmwflash").
static func texture_for(profile: String) -> Texture2D:
	if _cache.has(profile):
		return _cache[profile]
	var t: Texture2D = null
	var path := "%s/%s.png" % [DIR, profile]
	if not profile.is_empty() and ResourceLoader.exists(path):
		t = load(path)
	if t == null:
		t = placeholder()
	_cache[profile] = t
	return t


## The silhouette: the mock-up's SVG (viewBox 33 x 46, head r 7.5 at 16.5,17, shoulders
## from y 29) rasterised at 4x.
static func placeholder() -> ImageTexture:
	if _placeholder:
		return _placeholder
	var k := 4
	var w := 33 * k
	var h := 46 * k
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var bg := Color8(16, 34, 46)
	var fg := Color8(44, 74, 90)
	img.fill(bg)
	for y in h:
		for x in w:
			var p := Vector2(x + 0.5, y + 0.5) / k
			var head := p.distance_to(Vector2(16.5, 17.0)) <= 7.5
			# shoulders: a rounded mound from (3,46) up to (16.5,29) and back to (30,46)
			var half := 13.5 * sqrt(clampf((p.y - 29.0) / 17.0, 0.0, 1.0)) if p.y >= 29.0 else -1.0
			var body := half >= 0.0 and absf(p.x - 16.5) <= half
			if head or body:
				img.set_pixel(x, y, fg)
	_placeholder = ImageTexture.create_from_image(img)
	return _placeholder
