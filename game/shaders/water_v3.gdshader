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
uniform float glow = 0.0;         // per map (terrain_v3.json water_glow): the scattered colour added as light, for a low sun that leaves the sea black
uniform float spec_k = 1.0;        // per map (terrain_v3.json water_reflect): scales the sky reflection, so a sunset sky does not paint the sea orange
uniform float absorb_k = 1.0;      // per map (terrain_v3.json water_absorb_k): murkier water shows less of a dull bed and more of its own teal
uniform float art = 0.0;           // per map (water_shallow_col / water_deep_col keys): 1 = the colours are the artist's, lit by emission so a night or sunset light cannot turn them brown or black
uniform float art_emit = 0.35;     // per map (water_emit): how much of the artist's colour is self-lit
uniform float foam_k = 1.0;        // per map (water_foam): foam strength
uniform float foam_max_m = 0.0;    // per map (water_foam_m): the foam band is at most this many metres wide on the ground, however gentle the shore (0 = the pilot's depth-only band)
uniform float soft_m = 0.0;        // per map (water_depth_soft_m): metres over which the depth that drives the colour is averaged, so a 25.6 m facet step in the bed does not draw a straight lip
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
	if (soft_m > 0.0) bed = textureLod(screen_tex, ruv, clamp(vd / 2.0 - 1.0, 0.0, 5.0)).rgb;   // the bed seen through deeper water is soft, so a facet step in it does not draw a lip

	float vd_c = vd;   // the depth that drives the colour
	if (soft_m > 0.0) {
		float px = soft_m * PROJECTION_MATRIX[1][1] * VIEWPORT_SIZE.y * 0.5 / max(cam_d, 1.0);
		px = clamp(px, 1.0, 90.0);
		float acc = vd; float wsum = 1.0;
		for (int i = 0; i < 12; i++) {
			float ang = float(i) * 0.5236 + 0.4;
			float rr = px * (i % 2 == 0 ? 1.0 : 0.5);
			vec2 suv = SCREEN_UV + vec2(cos(ang), sin(ang)) * rr / VIEWPORT_SIZE;
			vec3 g = ground_world(suv, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX);
			acc += max(wp.y - g.y, 0.0); wsum += 1.0;
		}
		vd_c = acc / wsum;
	}
	vec3 tr = exp(-absorb * absorb_k * (soft_m > 0.0 ? rd * (vd_c / max(vd, 0.05)) : rd));
	float sc_t = 1.0 - exp(-vd_c / deep_m);
	vec3 scatter = mix(shallow_col, deep_col, sc_t);
	vec3 albedo = scatter * (vec3(1.0) - tr);
	vec3 emis = bed * tr;
	// the shore's slope (m of bed height per m of ground), from the screen-space derivatives of the rebuilt bed
	float sc = 1.0;
	if (foam_max_m > 0.0) {
		vec2 a1 = dFdx(gw.xz); vec2 a2 = dFdy(gw.xz);
		float det = a1.x * a2.y - a1.y * a2.x;
		float slope = 1.0;
		if (abs(det) > 1.0e-5) {
			vec2 g = vec2(dFdx(gw.y) * a2.y - dFdy(gw.y) * a1.y, a1.x * dFdy(gw.y) - a2.x * dFdx(gw.y)) / det;
			slope = clamp(length(g), 0.02, 1.0);
		}
		sc = clamp(slope * foam_max_m, 0.03, 1.0);
	}

	// ---- shore foam (round 2): thin, lacy, intermittent and not white. The depth is wandered with noise (metres, large
	// against the 25.6 m mesh's facet depth steps, so the foam's edge no longer traces triangles), a slow low-frequency gate
	// leaves stretches of shore bare, and a surge cycle breathes the band's width and strength so it comes and goes.
	float n1 = texture(foam_tex, wp.xz / 17.0 + TIME * vec2(0.012, -0.009)).r * 2.2;
	float n2 = texture(foam_tex, wp.zx / 6.0 - TIME * vec2(0.02, 0.007) + 0.4).r * 2.2;
	float n3 = texture(foam_tex, wp.xz / 70.0 + 0.2).r * 2.2;
	float gate = smoothstep(0.35, 0.8, n3);
	float surge = 0.5 + 0.5 * sin(TIME * 0.7 + n1 * 4.0 + n3 * 6.0);
	float vdw = vd / sc + (n1 - 0.55) * 1.3 + (n2 - 0.55) * 0.5;
	float fw = foam_width * (0.35 + 0.9 * surge);
	float edge = 1.0 - smoothstep(0.0, fw, vdw);
	float run = smoothstep(0.7, 0.98, sin((vdw * 1.1 - TIME * 0.3) * 6.2832) * 0.5 + 0.5) * (1.0 - smoothstep(fw * 0.8, fw * 3.0, vdw)) * 0.5;
	float dens = (edge * (0.45 + 0.9 * n2) + run * n1 * 0.6) * (0.3 + 0.7 * gate);
	float foam = smoothstep(0.12, 0.42, dens) * (0.45 + 0.55 * surge) * 0.9 * foam_k;
	albedo = mix(albedo, foam_col, foam);
	emis *= 1.0 - foam * 0.7;
	ALBEDO = albedo;
	EMISSION = emis + albedo * glow * (1.0 - foam) + (art > 0.5 ? scatter * (vec3(1.0) - tr) * art_emit * (1.0 - foam) : vec3(0.0));
	ROUGHNESS = mix(mix(0.10, 0.30, smoothstep(150.0, 900.0, cam_d)), 0.85, foam);
	SPECULAR = mix(0.5, 0.2, foam) * spec_k;
	METALLIC = 0.0;
	NORMAL = normalize((VIEW_MATRIX * vec4(wn, 0.0)).xyz);
	ALPHA = clamp(smoothstep(0.0, 0.2, vd) + foam, 0.0, 1.0);
}
