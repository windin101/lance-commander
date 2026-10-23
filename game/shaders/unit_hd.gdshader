shader_type spatial;
// v2 HD unit shader (HD rework, 2026-10-23; tools/art/hd_v2.py). One material per unit model and paint scheme
// (MechPaint.apply_scheme). Two ways to paint:
//   scheme_mode 0: the original's team mask (mask R/G = highlight 1/2 over the base), the mission's colours;
//   scheme_mode 1: a scheme by body region (player, Steiner, Liao: game/data/faction_paint.json), with inset
//                  piping, a leg stripe, a limb band and an optional camouflage pattern in the base regions.
// Over that: bare and dark metal, battle wear (chips and scratches on edges from the baked curvature, grime and runs
// in recesses from the AO, soot by weapons and vents, mud on the lower legs and feet, scorch blotches), stencil
// numbers and crest, glass (canopy), lenses and lights, the mission's dust and snow. Fine wear fades with distance so
// the RTS camera doesn't sparkle. Back faces (a joint opening) shade as a dark interior.
render_mode cull_disabled, depth_draw_opaque;

uniform sampler2D mask_tex : hint_default_black, filter_linear_mipmap_anisotropic;    // R hl1, G hl2, B metal tone, A glass code
uniform sampler2D mask_id_tex : hint_default_black, filter_nearest_mipmap;           // the same texture: exact glass codes
uniform sampler2D detail_tex : hint_default_white, filter_linear_mipmap_anisotropic;  // R AO, G curvature, B decal, A soot
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D zones_tex : hint_default_black, filter_linear_mipmap;              // R region, G piping, B stripe, A band
uniform sampler2D zones_id_tex : hint_default_black, filter_nearest_mipmap;          // the same texture: region ids
uniform sampler2D camo_tex : hint_default_white, filter_linear_mipmap;               // RGB object-space noise octaves
uniform sampler2D grunge_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform int scheme_mode = 0;
uniform vec3 base_colour : source_color = vec3(0.45, 0.47, 0.42);
uniform vec3 hl1_colour : source_color = vec3(0.6, 0.2, 0.12);
uniform vec3 hl2_colour : source_color = vec3(0.8, 0.65, 0.2);
// regions: 0 body, 1 head, 2 arms, 3 upper legs, 4 lower legs, 5 feet, 6 weapons, 7 plates
uniform vec3 region_colour[8];                       // linear (MechPaint converts from sRGB)
uniform float region_steel[8];
uniform float region_camo[8];
uniform vec3 piping_colour : source_color = vec3(0.8, 0.2, 0.1);
uniform float piping_on = 0.0;
uniform vec3 stripe_colour : source_color = vec3(0.6, 0.0, 0.0);
uniform float stripe_on = 0.0;
uniform vec3 band_colour : source_color = vec3(0.8, 0.2, 0.1);
uniform float band_on = 0.0;
uniform int pattern = 0;                             // 0 plain, 1 woodland, 2 snow, 3 urban, 4 thorin, 5 arkab
uniform vec3 decal_colour : source_color = vec3(0.86, 0.85, 0.8);
uniform float insignia_on = 0.0;
uniform vec3 emissive_colour : source_color = vec3(1.0, 0.72, 0.38);
uniform vec3 lens_colour : source_color = vec3(0.25, 1.0, 0.4);
uniform float emissive_energy = 3.0;

uniform float wear : hint_range(0.0, 1.0) = 1.0;    // chipped paint along edges
uniform float grime : hint_range(0.0, 1.0) = 0.95;    // dirt in recesses and runs
uniform float burns : hint_range(0.0, 1.0) = 0.45;   // scorch blotches
uniform float soot : hint_range(0.0, 1.0) = 0.8;     // by weapons and vents
uniform float mud : hint_range(0.0, 1.0) = 0.9;      // lower legs and feet
uniform vec3 mud_colour : source_color = vec3(0.24, 0.19, 0.14);
uniform float detail_near = 35.0;
uniform float detail_far = 110.0;
uniform float dust : hint_range(0.0, 1.0) = 0.25;
uniform float snow : hint_range(0.0, 1.0) = 0.0;
uniform vec3 dust_colour : source_color = vec3(0.56, 0.5, 0.4);
uniform float scorch : hint_range(0.0, 1.0) = 0.0;   // 1 = wreck
uniform float grunge_scale = 6.0;
uniform float height_m = 9.0;
instance uniform float unit_seed = 0.0;

uniform vec3 rest_min = vec3(0.0);
uniform vec3 rest_extent = vec3(1.0);
varying vec3 world_n;
varying float rel_h;
varying vec3 rest_p;

void vertex() {
	world_n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	rest_p = rest_min + COLOR.rgb * rest_extent;   // rest-pose position, metres (hd_v2 bakes it into COLOR)
	rel_h = (MODEL_MATRIX * vec4(VERTEX, 1.0)).y - MODEL_MATRIX[3].y;
}

vec3 camo_srgb(int pat, vec3 n, vec3 fallback) {
	// hard-edged painted blotches from the object-space noise octaves (n.r large, n.g medium, n.b small)
	float e = 0.025;
	if (pat == 1) {   // woodland: olive field, dark green and brown blotches, black streaks
		vec3 c = vec3(0.30, 0.33, 0.19);
		c = mix(c, vec3(0.13, 0.19, 0.10), smoothstep(0.56 - e, 0.56 + e, n.r));
		c = mix(c, vec3(0.31, 0.22, 0.13), smoothstep(0.64 - e, 0.64 + e, n.g));
		c = mix(c, vec3(0.06, 0.07, 0.05), smoothstep(0.70 - e, 0.70 + e, n.b) * step(n.r, 0.5));
		return c;
	} else if (pat == 2) {   // snow: white with light and mid grey splinters
		vec3 c = vec3(0.80, 0.82, 0.84);
		c = mix(c, vec3(0.60, 0.62, 0.65), smoothstep(0.60 - e, 0.60 + e, n.r));
		c = mix(c, vec3(0.40, 0.42, 0.45), smoothstep(0.68 - e, 0.68 + e, n.g));
		return c;
	} else if (pat == 3) {   // urban: greys and a blue-grey
		vec3 c = vec3(0.52, 0.53, 0.54);
		c = mix(c, vec3(0.33, 0.35, 0.39), smoothstep(0.55 - e, 0.55 + e, n.r));
		c = mix(c, vec3(0.17, 0.18, 0.19), smoothstep(0.63 - e, 0.63 + e, n.g));
		c = mix(c, vec3(0.70, 0.71, 0.72), smoothstep(0.72 - e, 0.72 + e, n.b));
		return c;
	} else if (pat == 4) {   // "thorin" (Davion): black-green, brown and tan blotches over the whole 'Mech
		vec3 c = vec3(0.29, 0.24, 0.14);
		c = mix(c, vec3(0.76, 0.67, 0.41), smoothstep(0.58 - e, 0.58 + e, n.r));
		c = mix(c, vec3(0.14, 0.165, 0.12), smoothstep(0.6 - e, 0.6 + e, n.g) * (1.0 - smoothstep(0.62, 0.66, n.r)));
		return c;
	} else if (pat == 5) {   // "arkab" (bandits): tan field, rust patches, faded dark-green desert blotches
		vec3 c = vec3(0.79, 0.65, 0.48);
		c = mix(c, vec3(0.6, 0.35, 0.16), smoothstep(0.6 - e, 0.6 + e, n.r));
		c = mix(c, vec3(0.37, 0.42, 0.27), smoothstep(0.66 - e, 0.66 + e, n.g) * 0.85);
		return c;
	}
	return fallback;
}

vec3 camo_colour(int pat, vec3 n, vec3 fallback) {
	// the palettes above are written in sRGB, as painted; the shader works in linear
	if (pat <= 0) {
		return fallback;
	}
	return pow(camo_srgb(pat, n, fallback), vec3(2.2));
}

vec4 tri(sampler2D t, vec3 p, vec3 n, float per_m) {
	// triplanar sample at per_m repeats a metre, blended by the (rest-frame) normal
	vec3 w = pow(abs(n), vec3(4.0));
	w /= (w.x + w.y + w.z);
	return texture(t, p.yz * per_m) * w.x + texture(t, p.xz * per_m + 0.37) * w.y + texture(t, p.xy * per_m + 0.71) * w.z;
}

void fragment() {
	vec4 m = texture(mask_tex, UV);
	vec4 d = texture(detail_tex, UV);
	vec4 z = texture(zones_tex, UV);
	float ao = d.r;
	float curv = d.g;
	float decal = d.b;
	vec3 gp = rest_p + vec3(unit_seed * 0.37, unit_seed * 0.11, 0.0);
	vec3 gn = normalize(cross(dFdx(rest_p), dFdy(rest_p)) + vec3(1e-5));
	vec4 g1 = tri(grunge_tex, gp, gn, 0.12);   // one tile per ~8 m: blotches 1-3 m
	vec4 g2 = tri(grunge_tex, gp, gn, 0.45);   // mottling ~0.5 m, chips ~3 cm
	vec4 g3 = tri(grunge_tex, gp, gn, 1.3);
	float near_ = 1.0 - smoothstep(detail_near, detail_far, length(VERTEX));

	// paint
	vec3 paint;
	float steel_region = 0.0;
	if (scheme_mode == 1) {
		int rid = clamp(int(texture(zones_id_tex, UV).r * 255.0 / 16.0), 0, 7);
		paint = region_colour[rid];
		steel_region = region_steel[rid];
		if (pattern > 0 && region_camo[rid] > 0.5) {
			paint = camo_colour(pattern, texture(camo_tex, UV).rgb, paint);
		}
		paint = mix(paint, band_colour, step(0.5, z.a) * band_on);
		paint = mix(paint, stripe_colour, step(0.5, z.b) * stripe_on);
		paint = mix(paint, piping_colour, smoothstep(0.35, 0.65, z.g) * piping_on);
	} else {
		paint = base_colour;
		paint = mix(paint, hl1_colour, m.r);
		paint = mix(paint, hl2_colour, m.g);
	}
	paint *= 0.9 + 0.2 * g1.g;
	paint = mix(paint, paint * vec3(1.08, 1.05, 0.95) + 0.03, smoothstep(0.55, 0.75, g1.r) * 0.5);   // sun-faded patches
	float metal_zone = max(smoothstep(0.12, 0.3, m.b), steel_region);
	float metal_tone = steel_region > 0.5 ? (m.b > 0.1 ? m.b : 0.7) : m.b;   // housings keep their dark gunmetal
	vec3 steel = mix(vec3(0.08, 0.08, 0.085), vec3(0.3, 0.305, 0.32), smoothstep(0.3, 0.9, metal_tone));
	steel *= 0.88 + 0.24 * g2.b;
	// wear: convex edges lose their paint down to bright scuffed steel; fine scratches across the panels
	float edge = smoothstep(0.515, 0.6, curv + (g2.b - 0.5) * 0.2);
	float chip = clamp(edge * wear * 2.6 - (1.0 - g2.b) * 0.9, 0.0, 1.0) * near_;
	chip = max(chip, smoothstep(0.78, 0.84, g3.b) * edge * near_);   // pitting along worn edges
	float scratch = smoothstep(0.82, 0.88, g2.a) * smoothstep(0.6, 0.8, g1.b) * wear * 0.45 * near_;
	chip = max(chip, scratch) * (1.0 - metal_zone) * (1.0 - smoothstep(0.02, 0.2, m.a));   // no white chips round the glass
	vec3 albedo = mix(paint, steel, metal_zone);
	vec3 bare = vec3(0.34, 0.34, 0.35) * (0.9 + 0.2 * g2.b);
	// stencil numbers, and the crest where the scheme has one
	float num = smoothstep(0.7, 0.85, decal);
	float crest = smoothstep(0.35, 0.45, decal) * (1.0 - smoothstep(0.6, 0.7, decal)) * insignia_on;
	albedo = mix(albedo, decal_colour, (num + crest) * (0.78 + 0.22 * g1.b));
	// a chip shows bright scuffed steel inside a dark lip of torn paint and primer, so it reads on any colour
	float lip = clamp(edge * wear * 2.6 - (1.0 - g2.b) * 0.6, 0.0, 1.0) * near_ * (1.0 - metal_zone);
	albedo = mix(albedo, albedo * 0.35, clamp(lip - chip, 0.0, 1.0) * 0.8);
	albedo = mix(albedo, bare * 1.25, chip);
	// recesses, panel lines and runs of grime
	float concave = smoothstep(0.42, 0.22, curv);   // well below neutral: curvature noise must not draw dark dots
	float cavity = clamp(smoothstep(0.12, 0.6, 1.0 - ao) * 1.1 + concave * 0.7, 0.0, 1.0);   // real recesses, not bake noise
	albedo *= 1.0 - concave * mix(0.2, 0.5, near_);
	vec3 dirt = albedo * vec3(0.3, 0.27, 0.22);
	float runs = smoothstep(0.5, 0.72, g2.a) * (0.5 + 0.5 * (1.0 - ao)) * (1.0 - clamp(world_n.y, 0.0, 1.0) * 0.6);
	albedo = mix(albedo, dirt, clamp((cavity * 1.1 + runs * 0.8) * grime, 0.0, 0.94));
	albedo *= mix(1.0, ao, 0.3);
	albedo = mix(albedo, albedo * 0.55, smoothstep(0.45, 0.75, g1.r) * smoothstep(0.3, 0.7, 1.0 - ao) * grime * 0.6);   // grime patches   // grime settles in every occluded corner
	// soot by weapons and vents; mud up the legs; scorch blotches; the wreck's burn
	float sootm = clamp(d.a * soot * (0.6 + 0.8 * g1.r), 0.0, 1.0);
	albedo = mix(albedo, vec3(0.03, 0.028, 0.025), sootm * 0.9);
	float low = 1.0 - smoothstep(height_m * 0.05, height_m * 0.26, rel_h + (g1.g - 0.5) * height_m * 0.1);
	float mudm = clamp(mud * low * smoothstep(0.35, 0.6, g2.g + (1.0 - low) * -0.2) * 1.1, 0.0, 0.9);
	albedo = mix(albedo, mud_colour * (0.85 + 0.3 * g2.g), mudm * 0.85);
	float blot = smoothstep(0.66, 0.8, g1.r + (g2.g - 0.5) * 0.2) * burns;
	albedo = mix(albedo, vec3(0.04, 0.035, 0.03), clamp(blot * 0.85 + scorch * 0.85, 0.0, 0.95));
	// mission layer
	float up = clamp(world_n.y, 0.0, 1.0);
	float lowd = 1.0 - smoothstep(0.0, height_m * 0.4, rel_h);
	float dmask = clamp(dust * (smoothstep(0.25, 0.9, up) * 0.8 + cavity * 0.5 + lowd * 0.9) * (0.55 + 0.9 * g1.g), 0.0, 1.0);
	albedo = mix(albedo, dust_colour * (0.85 + 0.3 * g2.g), dmask * 0.85);
	float smask = clamp(snow * smoothstep(0.35, 0.75, up + (g1.g - 0.5) * 0.4) * 1.6, 0.0, 1.0);
	albedo = mix(albedo, vec3(0.88, 0.9, 0.93), smask);

	float metallic = mix(0.08, mix(0.3, 0.75, smoothstep(0.3, 0.9, metal_tone)), max(metal_zone, chip)) * (1.0 - mudm * 0.8) * (1.0 - sootm * 0.6);
	float metal_rough = mix(0.72, 0.45, smoothstep(0.3, 0.9, metal_tone));   // dark gunmetal (housings) is satin, not chrome
	float rough = mix(0.58, metal_rough, max(metal_zone, chip)) + 0.12 * (g2.g - 0.5) + dmask * 0.3 + cavity * grime * 0.2
		+ mudm * 0.35 + sootm * 0.3;
	rough = mix(rough, 0.95, scorch);
	float code = texture(mask_id_tex, UV).a * 255.0;   // nearest: a linear blend at the edge made lens and light fringes
	if (!FRONT_FACING) {
		ALBEDO = vec3(0.025, 0.024, 0.023);
		METALLIC = 0.0;
		ROUGHNESS = 1.0;
		NORMAL = -NORMAL;
	} else if (code > 60.0) {
		// glass and lights: never paint, camo or dirt (a little dust on glass), glossy with a fresnel edge
		float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		METALLIC = 0.0;
		SPECULAR = 0.8;
		if (code > 220.0) {   // canopy: a dark tinted pane that mirrors a sky gradient, strongest at grazing angles
			vec3 rv = (INV_VIEW_MATRIX * vec4(reflect(-VIEW, NORMAL), 0.0)).xyz;
			vec3 sky = mix(vec3(0.07, 0.07, 0.08), mix(vec3(0.42, 0.5, 0.6), vec3(0.75, 0.82, 0.9), smoothstep(0.0, 0.7, rv.y)),
				smoothstep(-0.15, 0.05, rv.y));
			ALBEDO = vec3(0.01, 0.018, 0.03);
			ROUGHNESS = 0.03 + dmask * 0.3;
			SPECULAR = 1.0;
			EMISSION = sky * (0.12 + 0.85 * fres) * (1.0 - dmask * 0.7) * (1.0 - scorch);
		} else if (code > 150.0) {   // sensor lens
			ALBEDO = vec3(0.02, 0.06, 0.03);
			ROUGHNESS = 0.05;
			EMISSION = lens_colour * emissive_energy * (0.6 + 0.4 * fres) * (1.0 - scorch);
		} else {                     // light
			ALBEDO = vec3(0.1, 0.08, 0.05);
			ROUGHNESS = 0.08;
			EMISSION = emissive_colour * emissive_energy * (1.0 - scorch);
		}
		AO = ao;
	} else {
		ALBEDO = albedo;
		METALLIC = metallic * (1.0 - dmask * 0.7) * (1.0 - smask);
		ROUGHNESS = clamp(mix(rough + 0.08 * (1.0 - metal_zone), 0.7, smask), 0.05, 1.0);
		SPECULAR = mix(0.3, 0.5, max(metal_zone, chip));   // painted armour: low specular, no mirror of the hangar's cyan
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		AO = ao;
		AO_LIGHT_AFFECT = 0.55;
	}
}
