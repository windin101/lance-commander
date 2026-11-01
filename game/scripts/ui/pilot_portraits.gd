class_name PilotPortraits
extends RefCounted
## Pilot portrait lookup for the HUD (lance cards, comms). A generated face at
## assets/ui/portraits/<pilot profile>.png (and <profile>_wounded.png) wins when it exists; until those are made every
## pilot gets the silhouette placeholder of the approved mock-up (head and shoulders on the
## dark portrait well, 33:46).

const DIR := "res://assets/ui/portraits"
const WOUNDED_SUFFIX := "_wounded"  # <profile>_wounded.png: the drawn dressing variant (guide 7)
const TAC_OFFICER := "tacofficer"

static var _cache := {}
static var _placeholder: ImageTexture


## The art profile for a campaign profile: the pmp_<x> twins (the player's campaign pilots)
## share the pmw<x> faces.
static func art_profile(profile: String) -> String:
	if profile.begins_with("pmp_"):
		return "pmw" + profile.substr(4)
	return profile


## The res:// path for a profile's portrait (wounded variant or clean), whether or not it exists.
static func path_for(profile: String, wounded := false) -> String:
	return "%s/%s%s.png" % [DIR, art_profile(profile), WOUNDED_SUFFIX if wounded else ""]


## True when the unit's pilot is hurt but alive: the HUD then shows the wounded portrait.
static func is_wounded(unit) -> bool:
	return unit != null and unit.pilot != null and unit.pilot.wounds > 0.0 and not unit.pilot.dead


## The portrait for a pilot profile (SimUnit.pilot_profile, e.g. "pmwflash" or "pmp_flash").
## wounded asks for the dressing variant and falls back to the clean face when it is missing.
static func texture_for(profile: String, wounded := false) -> Texture2D:
	var key := path_for(profile, wounded)
	if _cache.has(key):
		return _cache[key]
	var t: Texture2D = null
	if not profile.is_empty() and ResourceLoader.exists(key):
		t = load(key)
	if t == null and wounded:
		t = texture_for(profile, false)
	if t == null:
		t = placeholder()
	_cache[key] = t
	return t


## The tac officer (tacofficer.png), or the silhouette until that file exists.
static func tac_officer() -> Texture2D:
	return texture_for(TAC_OFFICER)


## The face for a voice-over speaker: the tac officer for "Tac Officer" and for the unnamed
## command voice, the silhouette for anyone else.
static func texture_for_speaker(speaker: String) -> Texture2D:
	var s := speaker.strip_edges().to_lower()
	if s.is_empty() or s == "command" or s.contains("tac officer") or s == TAC_OFFICER:
		return tac_officer()
	return placeholder()


## The silhouette: the mock-up's SVG (viewBox 33 x 46, head r 7.5 at 16.5,17, shoulders
## from y 29) rasterised at 4x.
static func placeholder() -> ImageTexture:
	if _placeholder:
		return _placeholder
	var k := 4
	var w := 33 * k
	var h := 46 * k
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var bg := UiStyle.PORTRAIT_WELL  # guide 6 / 7: the portrait well
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
