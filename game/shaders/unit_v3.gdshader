shader_type spatial;
// v3 HD unit shader (Pipeline A, 2026-10-24; tools/art/v3/v3_mech.py). Everything that is detail is baked into the
// chassis textures (mipmapped, so stable at RTS distance); this shader only applies the paint scheme:
//   albedo_tex  RGB what shows where the paint doesn't (bare metal, chips, grime, dust, soot, glass), A paint coverage
//   orm_tex     R ambient occlusion, G roughness, B metallic, A paint shade (panel tone, cavities, chip lips)
//   normal_tex  baked tangent-space normals (the bevelled sculpt)
//   ids_tex     R region code (0-7 PaintScheme.REGIONS, 8 bare metal, 9 glass, 10 lens) sampled nearest;
//               G piping, B stripe, A limb band sampled linear (the same texture twice)
//   camo_tex    object-space pattern fields R/G/B (large/medium/small blotches), A exposure for mission dust/snow
// Paint: final = mix(albedo.rgb, scheme colour * shade, albedo.a). Paint is a matte dielectric; chips (albedo.a = 0)
// keep the bright steel and its metal/roughness flip from orm_tex.
render_mode depth_draw_opaque, cull_back;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D ids_tex : hint_default_black, filter_nearest_mipmap;
uniform sampler2D ids_lin_tex : hint_default_black, filter_linear_mipmap_anisotropic;
uniform sampler2D camo_tex : hint_default_white, filter_linear_mipmap;
uniform sampler2D detail_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;   // tiling micro detail

uniform vec3 region_colour[8];        // linear (MechPaint converts from sRGB)
uniform float region_steel[8];
uniform float region_camo[8];
uniform vec3 piping_colour : source_color = vec3(0.8, 0.2, 0.1);
uniform float piping_on = 0.0;
uniform vec3 stripe_colour : source_color = vec3(0.6, 0.0, 0.0);
uniform float stripe_on = 0.0;
uniform vec3 band_colour : source_color = vec3(0.8, 0.2, 0.1);
uniform float band_on = 0.0;
uniform int pattern = 0;              // 0 plain, 1 woodland, 2 snow, 3 urban, 4 thorin, 5 arkab
uniform vec3 steel_colour : source_color = vec3(0.30, 0.305, 0.32);
uniform vec3 glass_tint : source_color = vec3(0.05, 0.12, 0.16);
uniform vec3 lens_colour : source_color = vec3(1.0, 0.35, 0.15);
uniform float emissive_energy = 2.0;
uniform float glass_glow = 0.15;
uniform float dust : hint_range(0.0, 1.0) = 0.0;
uniform float snow : hint_range(0.0, 1.0) = 0.0;
uniform vec3 dust_colour : source_color = vec3(0.56, 0.5, 0.4);
uniform float scorch : hint_range(0.0, 1.0) = 0.0;   // 1 = wreck
uniform float detail_scale = 2.0;     // micro-detail tiles per UV unit x 100 (see MechPaint: px/m of the atlas)
uniform float detail_strength = 0.0;  // the Mech Bay/Lab turns it up; 0 in the field

vec3 srgb(vec3 c) { return pow(c, vec3(2.2)); }

vec3 camo(int pat, vec3 n, vec3 base, float aa) {
	// hard-edged blotches from the baked pattern fields; the edge width follows the screen-space derivative
	if (pat == 1) {
		vec3 c = srgb(vec3(0.30, 0.33, 0.19));
		c = mix(c, srgb(vec3(0.13, 0.19, 0.10)), smoothstep(0.56 - aa, 0.56 + aa, n.r));
		c = mix(c, srgb(vec3(0.31, 0.22, 0.13)), smoothstep(0.64 - aa, 0.64 + aa, n.g));
		c = mix(c, srgb(vec3(0.06, 0.07, 0.05)), smoothstep(0.70 - aa, 0.70 + aa, n.b));
		return c;
	} else if (pat == 2) {
		vec3 c = srgb(vec3(0.80, 0.82, 0.84));
		c = mix(c, srgb(vec3(0.60, 0.62, 0.65)), smoothstep(0.60 - aa, 0.60 + aa, n.r));
		c = mix(c, srgb(vec3(0.40, 0.42, 0.45)), smoothstep(0.68 - aa, 0.68 + aa, n.g));
		return c;
	} else if (pat == 3) {
		vec3 c = srgb(vec3(0.52, 0.53, 0.54));
		c = mix(c, srgb(vec3(0.33, 0.35, 0.39)), smoothstep(0.55 - aa, 0.55 + aa, n.r));
		c = mix(c, srgb(vec3(0.17, 0.18, 0.19)), smoothstep(0.63 - aa, 0.63 + aa, n.g));
		c = mix(c, srgb(vec3(0.70, 0.71, 0.72)), smoothstep(0.72 - aa, 0.72 + aa, n.b));
		return c;
	} else if (pat == 4) {
		vec3 c = srgb(vec3(0.29, 0.24, 0.14));
		c = mix(c, srgb(vec3(0.76, 0.67, 0.41)), smoothstep(0.58 - aa, 0.58 + aa, n.r));
		c = mix(c, srgb(vec3(0.14, 0.165, 0.12)), smoothstep(0.60 - aa, 0.60 + aa, n.g));
		return c;
	} else if (pat == 5) {
		vec3 c = srgb(vec3(0.79, 0.65, 0.48));
		c = mix(c, srgb(vec3(0.6, 0.35, 0.16)), smoothstep(0.6 - aa, 0.6 + aa, n.r));
		c = mix(c, srgb(vec3(0.37, 0.42, 0.27)), smoothstep(0.66 - aa, 0.66 + aa, n.g) * 0.85);
		return c;
	}
	return base;
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	vec4 orm = texture(orm_tex, UV);
	int rid = int(texture(ids_tex, UV).r * 255.0 + 0.5) / 16;
	vec4 idl = texture(ids_lin_tex, UV);
	vec4 cm = texture(camo_tex, UV);
	float paint_a = rid < 8 ? a.a : 0.0;
	int r = clamp(rid, 0, 7);
	vec3 paint = region_colour[r];
	float steel = region_steel[r];
	if (pattern > 0 && region_camo[r] > 0.5) {
		float aa = clamp(fwidth(cm.r) * 1.5, 0.01, 0.12);
		paint = camo(pattern, cm.rgb, paint, aa);
	}
	paint = mix(paint, band_colour, smoothstep(0.35, 0.65, idl.a) * band_on);
	paint = mix(paint, stripe_colour, smoothstep(0.35, 0.65, idl.b) * stripe_on);
	paint = mix(paint, piping_colour, smoothstep(0.35, 0.65, idl.g) * piping_on);
	paint = mix(paint, steel_colour, steel);
	paint *= orm.a * 1.25;
	vec3 col = mix(a.rgb, paint, paint_a);
	float metal = mix(orm.b, 0.8, steel * paint_a);
	float rough = mix(orm.g, 0.42, steel * paint_a);
	// the mission's dust and snow settle on what faces up and on the legs
	float cover = clamp(cm.a * 1.2 - 0.15, 0.0, 1.0);
	col = mix(col, dust_colour, cover * dust * 0.6);
	rough = mix(rough, 0.9, cover * dust * 0.5);
	col = mix(col, vec3(0.82, 0.85, 0.88), smoothstep(0.35, 0.75, cover) * snow);
	vec3 emit = vec3(0.0);
	if (rid == 9) {
		col = glass_tint; metal = 0.0; rough = 0.04;
		emit = glass_tint * glass_glow;
	} else if (rid == 10) {
		emit = lens_colour * emissive_energy;
	}
	col *= mix(1.0, 0.22, scorch);
	rough = mix(rough, 0.95, scorch * 0.7);
	metal *= 1.0 - scorch * 0.7;
	ALBEDO = col;
	METALLIC = metal;
	ROUGHNESS = rough;
	SPECULAR = rid == 9 ? 0.9 : 0.5;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.15;
	vec3 nm = texture(normal_tex, UV).rgb;
	if (detail_strength > 0.0) {
		vec3 d = texture(detail_tex, UV * detail_scale * 100.0).rgb * 2.0 - 1.0;
		vec3 b = nm * 2.0 - 1.0;
		b.xy += d.xy * detail_strength;
		nm = normalize(b) * 0.5 + 0.5;
	}
	NORMAL_MAP = nm;
	EMISSION = emit;
}
