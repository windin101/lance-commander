shader_type spatial;
// v2 HD unit shader (HD rework, 2026-10-23; tools/art/hd_v2.py). One material per unit model and paint scheme
// (MechPaint.apply). Team paint from the mission's three colours, bare and dark metal, battle wear from the baked
// curvature (chipped edges), grime from the baked AO, panel lines from concave curvature, scorch blotches, stencil
// decals, emissive lights, and the mission's dust and snow layer (MechPaint.env_*). Back faces (looking into a
// part through a joint opening) shade as a dark interior instead of showing the far side.
render_mode cull_disabled, depth_draw_opaque;

uniform sampler2D mask_tex : hint_default_black, filter_linear_mipmap_anisotropic;    // R hl1, G hl2, B metal tone, A emissive
uniform sampler2D detail_tex : hint_default_white, filter_linear_mipmap_anisotropic;  // R AO, G curvature (0.5 flat), B decal
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D grunge_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform vec3 base_colour : source_color = vec3(0.45, 0.47, 0.42);
uniform vec3 hl1_colour : source_color = vec3(0.6, 0.2, 0.12);
uniform vec3 hl2_colour : source_color = vec3(0.8, 0.65, 0.2);
uniform vec3 decal_colour : source_color = vec3(0.86, 0.85, 0.8);
uniform vec3 emissive_colour : source_color = vec3(1.0, 0.72, 0.38);
uniform float emissive_energy = 3.0;

uniform float wear : hint_range(0.0, 1.0) = 0.5;     // chipped paint along edges
uniform float detail_near = 35.0;                    // metres from the camera: full wear and panel lines
uniform float detail_far = 110.0;                    // beyond: averaged out
uniform float grime : hint_range(0.0, 1.0) = 0.6;    // dirt in recesses and runs
uniform float burns : hint_range(0.0, 1.0) = 0.35;   // scorch blotches
uniform float dust : hint_range(0.0, 1.0) = 0.25;    // mission layer
uniform float snow : hint_range(0.0, 1.0) = 0.0;     // mission layer
uniform vec3 dust_colour : source_color = vec3(0.56, 0.5, 0.4);
uniform float scorch : hint_range(0.0, 1.0) = 0.0;   // 1 = wreck
uniform float grunge_scale = 6.0;                    // grunge repeats per UV unit
uniform float height_m = 9.0;                        // unit height, for dust rising from the feet
instance uniform float unit_seed = 0.0;

varying vec3 world_n;
varying float rel_h;

void vertex() {
	world_n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	rel_h = (MODEL_MATRIX * vec4(VERTEX, 1.0)).y - MODEL_MATRIX[3].y;
}

void fragment() {
	vec4 m = texture(mask_tex, UV);
	vec4 d = texture(detail_tex, UV);
	float ao = d.r;
	float curv = d.g;
	float decal = d.b;
	vec2 gu = UV * grunge_scale + vec2(unit_seed * 0.137, unit_seed * 0.071);
	vec4 g1 = texture(grunge_tex, gu);
	vec4 g2 = texture(grunge_tex, UV * grunge_scale * 3.7 + vec2(0.31, 0.77));

	// paint: base, then the two highlights, a gentle fade mottling
	vec3 paint = base_colour;
	paint = mix(paint, hl1_colour, m.r);
	paint = mix(paint, hl2_colour, m.g);
	paint *= 0.88 + 0.24 * g1.g;
	float metal_zone = smoothstep(0.12, 0.3, m.b);
	vec3 steel = mix(vec3(0.13, 0.13, 0.14), vec3(0.3, 0.305, 0.32), smoothstep(0.3, 0.9, m.b));
	steel *= 0.85 + 0.3 * g2.b;
	// fine detail fades with distance: at the RTS camera a unit is a few hundred pixels and sub-pixel chips and
	// panel lines would only sparkle (the import's mesh LODs take the geometry down the same way)
	float near_ = 1.0 - smoothstep(detail_near, detail_far, length(VERTEX));
	// wear: convex edges lose paint, broken up by fine noise
	float edge = smoothstep(0.54, 0.78, curv + (g2.b - 0.5) * 0.35);
	float chip = clamp(edge * wear * 1.6 - (1.0 - g1.b) * 0.6, 0.0, 1.0) * near_;
	chip *= 1.0 - metal_zone;
	vec3 albedo = mix(paint, steel, metal_zone);
	albedo = mix(albedo, vec3(0.33, 0.33, 0.34) * (0.8 + 0.4 * g2.b), chip);
	// stencil decals (worn with the paint)
	albedo = mix(albedo, decal_colour, smoothstep(0.35, 0.65, decal) * (1.0 - chip) * (0.75 + 0.25 * g1.b));
	// panel lines and recesses: concave curvature and AO
	float concave = smoothstep(0.46, 0.25, curv);
	float cavity = clamp((1.0 - ao) * 1.1 + concave * 0.6, 0.0, 1.0);
	albedo *= 1.0 - concave * mix(0.15, 0.45, near_);
	vec3 dirt = albedo * vec3(0.34, 0.3, 0.25);
	float runs = smoothstep(0.55, 0.8, g1.a) * 0.5;
	albedo = mix(albedo, dirt, clamp((cavity * 0.9 + runs * (1.0 - ao + 0.3)) * grime, 0.0, 0.92));
	// scorch blotches, and the wreck's burn
	float blot = smoothstep(0.66, 0.8, g1.r + (g2.g - 0.5) * 0.2) * burns;
	albedo = mix(albedo, vec3(0.04, 0.035, 0.03), clamp(blot * 0.85 + scorch * 0.85, 0.0, 0.95));
	// mission layer: dust on top faces, in recesses and rising from the feet; snow on top faces
	float up = clamp(world_n.y, 0.0, 1.0);
	float low = 1.0 - smoothstep(0.0, height_m * 0.4, rel_h);
	float dmask = clamp(dust * (smoothstep(0.25, 0.9, up) * 0.8 + cavity * 0.5 + low * 0.9) * (0.55 + 0.9 * g1.g), 0.0, 1.0);
	albedo = mix(albedo, dust_colour * (0.85 + 0.3 * g2.g), dmask * 0.85);
	float smask = clamp(snow * smoothstep(0.35, 0.75, up + (g1.g - 0.5) * 0.4) * 1.6, 0.0, 1.0);
	albedo = mix(albedo, vec3(0.88, 0.9, 0.93), smask);

	float metallic = mix(0.12, 0.85, max(metal_zone, chip));
	float rough = mix(0.58, 0.38, max(metal_zone, chip)) + 0.12 * (g2.g - 0.5) + dmask * 0.3 + cavity * grime * 0.15;
	rough = mix(rough, 0.95, scorch);
	if (FRONT_FACING) {
		ALBEDO = albedo;
		METALLIC = metallic * (1.0 - dmask * 0.7) * (1.0 - smask);
		ROUGHNESS = clamp(mix(rough, 0.7, smask), 0.05, 1.0);
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		AO = ao;
		AO_LIGHT_AFFECT = 0.55;
		EMISSION = emissive_colour * m.a * emissive_energy * (1.0 - scorch);
	} else {
		ALBEDO = vec3(0.025, 0.024, 0.023);
		METALLIC = 0.0;
		ROUGHNESS = 1.0;
		NORMAL = -NORMAL;
	}
}
