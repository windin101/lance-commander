class_name TerrainV3
extends RefCounted
## Switch for the v3 terrain (T3, LAN-68, 2026-10-25): the lit PBR ground (res://shaders/terrain_v3.gdshader) from
## res://assets/terrain/v3/<map>/. Off by default until Lee approves the pilot. On with the user argument
## --terrain-v3, the environment variable MC2_TERRAIN_V3=1, or [terrain] v3=true in user://dev.cfg. Maps without v3
## data keep the current ground either way.

static var enabled: bool = _detect()


static func _detect() -> bool:
	var args := OS.get_cmdline_user_args()
	if args.has("--no-terrain-v3") or OS.get_environment("MC2_TERRAIN_V3") == "0":
		return false
	if args.has("--terrain-v3") or OS.get_environment("MC2_TERRAIN_V3") == "1":
		return true
	var cfg := ConfigFile.new()
	if cfg.load("user://dev.cfg") == OK:
		return bool(cfg.get_value("terrain", "v3", false))
	return false


## How strongly a saturated mission sun is pulled toward a neutral key of the same brightness (0 = the mission's own
## colour, 1 = fully neutral above the threshold). Lee, 2026-10-25 (T3 review, option a): sunset maps such as
## mc2_14 (255, 106, 43) should read warm, not orange. Daylight suns (saturation <= SUN_SOFTEN_FROM) are untouched.
const SUN_SOFTEN := 1.0
const SUN_SOFTEN_FROM := 0.15


## The mission sun colour as v3 lights with it: hue and brightness kept, saturation above SUN_SOFTEN_FROM pulled
## toward grey by SUN_SOFTEN (luminance-preserving), so the warmth keeps its direction.
static func soften_light(c: Color) -> Color:
	if OS.get_cmdline_user_args().has("--no-sun-soften"):  # dev: review the mission's raw sun under v3
		return c
	# saturation above SUN_SOFTEN_FROM is cut by SUN_SOFTEN (1 = capped at SUN_SOFTEN_FROM); hue kept; luminance kept
	var s_new := c.s - SUN_SOFTEN * maxf(c.s - SUN_SOFTEN_FROM, 0.0)
	var out := Color.from_hsv(c.h, s_new, c.v)
	var y := c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722
	var y2 := out.r * 0.2126 + out.g * 0.7152 + out.b * 0.0722
	return out * (y / maxf(y2, 1e-4))


## The light's chroma at unit luminance (for keeping painted greys grey under a tinted sun).
static func chroma(c: Color) -> Vector3:
	var y := maxf(c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722, 1e-4)
	return Vector3(c.r, c.g, c.b) / y


## The same softening for the rest of a v3-lit environment: the sky's share of the ambient light (a sunset panorama,
## mc2_14 sky09 averages (162, 125, 78), lit everything orange even after the sun was softened) drops in proportion to
## the sky's saturation above SUN_SOFTEN_FROM, the flat ambient takes its place in the mission's (softened) ambient
## colour, and the fog colour is softened like the sun. Daylight skies are untouched.
static func soften_environment(env: Environment, sky_mean: Color) -> void:
	if OS.get_cmdline_user_args().has("--no-sun-soften"):
		return
	var excess := maxf(sky_mean.s - SUN_SOFTEN_FROM, 0.0) / (1.0 - SUN_SOFTEN_FROM)
	if excess <= 0.0:
		return
	env.ambient_light_sky_contribution = env.ambient_light_sky_contribution * clampf(1.0 - SUN_SOFTEN * excess * 1.6, 0.15, 1.0)
	env.ambient_light_color = soften_light(env.ambient_light_color)
	env.fog_light_color = soften_light(env.fog_light_color)


## Overall brightening for v3-lit missions (Lee, 2026-10-25, option a): the old ground was drawn unlit at full
## brightness, so a lit scene under a low or dim sun (mc2_14: 20 deg, sunset) reads far darker than the map did.
## The "key" is the sun's luminance times the sine of its elevation; against a bright 50-degree daylight key
## (EXPOSURE_REF_KEY) the lift is (ref / key) ^ EXPOSURE_GAMMA, clamped to 1 .. EXPOSURE_MAX_LIFT. Shadow direction and
## length are untouched (only exposure and ambient fill change). Returns [exposure multiplier, ambient multiplier].
const EXPOSURE_REF_KEY := 0.62
const EXPOSURE_GAMMA := 1.15
const EXPOSURE_MAX_LIFT := 4.0
const AMBIENT_FILL := 0.6   # share of the lift that goes to extra ambient fill (shadows lift more than lit faces)


const NIGHT_MAX_LIFT := 1.0   # night missions (sun below the horizon, pitch 270, or a dim moonlight key) keep their dark


static func exposure_for(sun: Color, pitch_deg: float) -> Vector2:
	if OS.get_cmdline_user_args().has("--no-v3-exposure"):
		return Vector2.ONE
	var p := fposmod(pitch_deg, 360.0)
	# Night is a dim sun (moonlight keys: mc2_05, 21, 23) or one below the horizon (pitch 182..358, 270 in the originals).
	# A bright sun at pitch 0 or 180 (mc2_10, mc2_19) is a grazing DAY sun: mission_view builds it at an elevation of
	# asin(0.2 / |(cos, 0.2, sin)|) (about 11 deg), so the key uses that, not sin(180) = 0 (which read as night and left
	# mc2_10, white sun and ambient 192, under the night cap with a flat dark ground).
	var below_horizon := p > 182.0 and p < 358.0
	if (below_horizon or maxf(sun.r, sun.g) < 0.5) and not OS.get_cmdline_user_args().has("--no-night-cap"):   # night: the old formula read sin(270) as a dim sun and lifted x4
		return Vector2(NIGHT_MAX_LIFT, NIGHT_MAX_LIFT)
	var lum := sun.r * 0.2126 + sun.g * 0.7152 + sun.b * 0.0722
	var elev := maxf(absf(sin(deg_to_rad(pitch_deg))), 0.2)   # the same floor mission_view puts on the sun's height
	var key := maxf(lum * elev, 0.02)
	var lift := clampf(pow(EXPOSURE_REF_KEY / key, EXPOSURE_GAMMA), 1.0, EXPOSURE_MAX_LIFT)
	return Vector2(pow(lift, 0.85), pow(lift, AMBIENT_FILL))
