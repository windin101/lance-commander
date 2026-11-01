shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;
// Water v3 (terrain polish, 2026-11-01). The flat water plane of the sim (level unchanged) drawn as a modern water
// surface; the old per-vertex-alpha plane stays behind --old-water (water.gdshader).
//   depth      read back from the depth buffer: the ground under each pixel is rebuilt in world space, so the water's
//              vertical and ray depth, the shoreline and the contact with anything standing in it are exact, whatever
//              the 25.6 m ground mesh does (no per-vertex alpha, so no grey haze at the shore)
//   colour     Beer-Lambert absorption of the lit scene behind it (the bed shows through the shallows, red goes first),
//              a scattered shallow-to-deep colour on top, both from the mission's own water tint (water.tga mean)
//   surface    three scrolling procedural normal layers in world space (swell, chop, ripple), flattened with distance
//              so far water does not shimmer; the sun glints and the sky reflection come from the PBR pipeline
//              (low roughness, Fresnel), nothing is faked
//   shore      depth-driven foam: a bubbly band at the contact line plus slow waves running up the beach, and foam
//              rings round whatever wades in it; the edge fades out so the ground meets the water softly

uniform sampler2D depth_tex : hint_depth_texture, repeat_disable, filter_nearest;
uniform sampler2D screen_tex : hint_screen_texture, repeat_disable, filter_linear_mipmap;
uniform sampler2D wave_n : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D foam_tex : filter_linear_mipmap, repeat_enable;

uniform vec3 shallow_col : source_color = vec3(0.06, 0.30, 0.30);
uniform vec3 deep_col : source_color = vec3(0.01, 0.07, 0.12);
uniform vec3 absorb = vec3(0.26, 0.075, 0.05);   // 1/m per channel
uniform float deep_m = 9.0;          // depth at which the scattered colour is 63 % deep
uniform float foam_width = 1.0;      // m of vertical depth
uniform vec3 foam_col : source_color = vec3(0.50, 0.55, 0.56);
uniform float swell_amp = 0.22;
uniform float chop_amp = 0.22;
uniform float ripple_amp = 0.12;
uniform float refract_k = 0.035;
uniform vec2 flow = vec2(0.9, 0.55);   // m/s drift of the swell layer

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

vec3 ground_world(vec2 suv, mat4 inv_proj, mat4 inv_view) {
	float d = textureLod(depth_tex, suv, 0.0).r;
	vec4 v = inv_proj * vec4(suv * 2.0 - 1.0, d, 1.0);
	v.xyz /= v.w;
	return (inv_view * vec4(v.xyz, 1.0)).xyz;
}

void fragment() {
	vec3 wp = wpos;
	float cam_d = length(wp - CAMERA_POSITION_WORLD);
	// ---- surface normal: three world-space layers, finer ones fade out with distance
	float f_chop = 1.0 - smoothstep(180.0, 700.0, cam_d);
	float f_rip = 1.0 - smoothstep(60.0, 260.0, cam_d);
	vec2 a = texture(wave_n, wp.xz / 53.0 + TIME * flow / 53.0).rg * 2.0 - 1.0;
	vec2 b = texture(wave_n, wp.zx / 17.0 - TIME * vec2(0.5, 0.8) / 17.0 + 0.31).rg * 2.0 - 1.0;
	vec2 c = texture(wave_n, wp.xz / 5.3 + TIME * vec2(-0.35, 0.6) / 5.3 + 0.67).rg * 2.0 - 1.0;
	vec2 slope = a * swell_amp + b * chop_amp * f_chop + c * ripple_amp * f_rip;
	vec3 wn = normalize(vec3(slope.x, 1.0, slope.y));

	// ---- depth under this pixel
	vec3 gw = ground_world(SCREEN_UV, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX);
	float vd = max(wp.y - gw.y, 0.0);       // vertical water depth where the view ray meets the bed
	float rd = length(gw - wp);             // path through the water
	if (gw.y > wp.y) { vd = 0.0; rd = 0.0; }

	// ---- refracted bed (only where the refracted ray still ends under the water)
	vec2 ruv = SCREEN_UV + slope * refract_k * clamp(vd / 2.5, 0.0, 1.0) * (1.0 - smoothstep(80.0, 400.0, cam_d));
	vec3 gw2 = ground_world(ruv, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX);
	if (gw2.y > wp.y - 0.02 || distance(gw2, CAMERA_POSITION_WORLD) < cam_d - 0.5) ruv = SCREEN_UV;
	vec3 bed = textureLod(screen_tex, ruv, 0.0).rgb;

	vec3 tr = exp(-absorb * rd);
	float sc_t = 1.0 - exp(-vd / deep_m);
	vec3 scatter = mix(shallow_col, deep_col, sc_t);
	vec3 albedo = scatter * (vec3(1.0) - tr);
	vec3 emis = bed * tr;

	// ---- shore foam (round 2): thin, lacy, intermittent and not white. The depth is wandered with noise (metres, large
	// against the 25.6 m mesh's facet depth steps, so the foam's edge no longer traces triangles), a slow low-frequency gate
	// leaves stretches of shore bare, and a surge cycle breathes the band's width and strength so it comes and goes.
	float n1 = texture(foam_tex, wp.xz / 17.0 + TIME * vec2(0.012, -0.009)).r * 2.2;
	float n2 = texture(foam_tex, wp.zx / 6.0 - TIME * vec2(0.02, 0.007) + 0.4).r * 2.2;
	float n3 = texture(foam_tex, wp.xz / 70.0 + 0.2).r * 2.2;
	float gate = smoothstep(0.35, 0.8, n3);
	float surge = 0.5 + 0.5 * sin(TIME * 0.7 + n1 * 4.0 + n3 * 6.0);
	float vdw = vd + (n1 - 0.55) * 1.3 + (n2 - 0.55) * 0.5;
	float fw = foam_width * (0.35 + 0.9 * surge);
	float edge = 1.0 - smoothstep(0.0, fw, vdw);
	float run = smoothstep(0.7, 0.98, sin((vdw * 1.1 - TIME * 0.3) * 6.2832) * 0.5 + 0.5) * (1.0 - smoothstep(fw * 0.8, fw * 3.0, vdw)) * 0.5;
	float dens = (edge * (0.45 + 0.9 * n2) + run * n1 * 0.6) * (0.3 + 0.7 * gate);
	float foam = smoothstep(0.12, 0.42, dens) * (0.45 + 0.55 * surge) * 0.9;
	albedo = mix(albedo, foam_col, foam);
	emis *= 1.0 - foam * 0.7;
	ALBEDO = albedo;
	EMISSION = emis;
	ROUGHNESS = mix(mix(0.10, 0.30, smoothstep(150.0, 900.0, cam_d)), 0.85, foam);
	SPECULAR = mix(0.5, 0.2, foam);
	METALLIC = 0.0;
	NORMAL = normalize((VIEW_MATRIX * vec4(wn, 0.0)).xyz);
	ALPHA = clamp(smoothstep(0.0, 0.2, vd) + foam, 0.0, 1.0);
}
