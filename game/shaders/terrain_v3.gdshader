shader_type spatial;
render_mode cull_back;
// Terrain v3 (T3, LAN-68, behind --terrain-v3; terrain_view.gd _v3_material). A lit PBR ground: the sun, the sky
// ambient and the v3 environment all apply (no light() override, no ambient_light_disabled). Data from
// tools/art/terrain/terrain_pack.py:
//   splat      2 m per texel: R top class, G second class, B blend toward the second (terrain_splat.py)
//   tint       the map's low-pass de-lit colour relative to its own mean (128 = 1.0): weak map identity only
//   layers_ah  8 layers (palette slots) RGB albedo + A height   } Texture2DArray, BPTC
//   layers_nr  RGB normal (OpenGL) + A roughness               }
// Per pixel: the 4 nearest splat texels give bilinear weights per class; the two strongest classes are
// height-blended. Each layer is detiled (Quilez, "texture repetition" technique 3: a low-frequency index picks a
// per-region offset, two lookups blend across it), triplanar on slopes steeper than about 35 degrees, and fades to
// its own mean colour far out (no shimmer). Roads, runways, bridges and cement are drawn on top exactly as
// terrain.gdshader draws them.

uniform sampler2D splat : filter_nearest, repeat_disable;
uniform sampler2D tint : filter_linear_mipmap, repeat_disable;
uniform sampler2DArray layers_ah : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layers_nr : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D variation : filter_linear_mipmap, repeat_enable;   // low-frequency noise for the detiling index
uniform float tile_m[8];
uniform vec3 mean_albedo[8];      // linear
// mixed maps (palettes.json "palette2"): a second palette in the same class slots where mask2 says so (snowfields)
uniform sampler2DArray layers2_ah : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layers2_nr : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D mask2 : filter_linear_mipmap, repeat_disable;
uniform float tile2_m[8];
uniform vec3 mean2_albedo[8];
uniform bool has_p2 = false;
// recovered mid-scale relief (tools/art/terrain/relief.py): RG macro normal x, z; B cavity AO
uniform sampler2D relief : filter_linear_mipmap, repeat_disable;
uniform bool has_relief = false;
// arid dunes (erosion.py ripple.png, RG normal x, z): faded out with distance, at RTS range they read as corduroy
uniform sampler2D ripple : filter_linear_mipmap, repeat_disable;
uniform bool has_ripple = false;
uniform float ripple_fade_start = 150.0;
uniform float ripple_fade_end = 260.0;
uniform float relief_strength = 1.0;
uniform float ao_strength = 0.8;
uniform vec3 sun_dir = vec3(0.4, 0.6, -0.5);   // toward the light (mission_view sets it)
uniform float relief_shade = 1.0;
uniform float relief_value = 0.0;   // (old shape-from-shading value channel; relief.png A is now curvature)
uniform float curvature_shade = 0.35;   // ridges a touch lighter, gullies darker (erosion.py curvature)
uniform float albedo_gain = 1.0;   // per map (terrain_pack.py albedo_gain): the map's overall value   // the band's painted value (gullies, crater shadows)   // the macro relief's own N.L contrast, as the burn-in had it (ambient fill would flatten it)
uniform float rough_scale[8];
uniform float albedo_scale[8];
uniform float map_side_m = 2560.0;
uniform float splat_px = 1280.0;
uniform float tint_strength = 0.7;
uniform float mask2_edge = 0.0;   // > 0: sharpen the second palette's mask edge (smoothstep half-width about 0.5). A dim dusk snowfield with a soft mask edge reads as a glowing fog (mc2_19)
uniform float snow_tint_neutral = 0.0;   // 1: the tint loses its colour under the second (snow) palette, so snow reads white-grey, not the blue of the original's burnt-in snow
uniform float blend_depth = 0.5;
uniform float rough_floor = 0.72;
uniform float shadow_fill = 0.05;   // a floor of the ground's own colour in deep cast shadow (airless maps: mc2_13 went pure black)
uniform float wear_strength = 0.9;
uniform float dusty_strength = 0.7;
uniform float specular = 0.25;
uniform float normal_strength = 1.0;
uniform float tri_start = 0.55;   // facet.y below: triplanar (cos 57 deg .. cos 33 deg)
uniform float tri_end = 0.82;
uniform float far_start = 700.0;
uniform float far_end = 1600.0;
uniform float macro_var = 0.55;   // large-scale value variation (MW5 rule: vary value, not hue)
uniform float warp_m = 14.0;      // splat border warp, metres (a second octave at warp_m / 3.5)
uniform float macro_ratio = 14.0; // the macro tiling of each layer, in tiles (about 20-40 m)
uniform float macro_near = 0.55;  // macro strength up close, rising to 1 by macro_far_m
uniform float macro_far_m = 350.0;
uniform vec3 light_chroma = vec3(1.0);   // the sun's chroma at unit luminance: painted greys (overlays, cement) are divided by it
uniform int debug_view = 0;       // 1 = classes, 2 = blend, 3 = tint, 4 = far fade
// overlays and cement, as terrain.gdshader
uniform sampler2D overlay_atlas : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D overlay_index : filter_nearest;
uniform sampler2D cement_weight : filter_linear;
uniform float atlas_cols = 22.0;
uniform float atlas_tile = 64.0;
uniform float atlas_pad = 2.0;
uniform float vertices_per_side = 0.0;

// T7 (LAN-72): modern paving (tools/art/terrain/paved_pack.py). 0 = concrete, 1 = asphalt, 2 = gravel track
uniform sampler2DArray paved_ah : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray paved_nr : filter_linear_mipmap_anisotropic, repeat_enable;
uniform float paved_tile_m[3];
uniform bool paved_v3 = false;
uniform float slab_m = 5.5;
uniform float kerb_strength = 0.85;
uniform sampler2D apron_sdf : filter_linear, repeat_disable;   // metres to the ragged apron edge, + inside (terrain_pack.py --apron)
uniform bool apron_on = false;
uniform float apron_spread = 8.0;
uniform sampler2D markings : filter_linear_mipmap, repeat_disable;   // R white SDF, G yellow SDF, B asphalt SDF, A track
uniform sampler2D markings_index : filter_nearest;
uniform float mk_cols = 0.0;
uniform float mk_tile = 384.0;
uniform float mk_pad = 8.0;
uniform float mk_spread = 0.3;

const vec3 DEBUG_RGB[8] = {vec3(0.67, 0.59, 0.35), vec3(0.35, 0.59, 0.24), vec3(0.55, 0.51, 0.47), vec3(0.35, 0.33, 0.31),
	vec3(0.78, 0.67, 0.47), vec3(0.92, 0.84, 0.63), vec3(0.16, 0.35, 0.16), vec3(0.24, 0.35, 0.55)};

varying vec3 world_pos;
varying vec3 world_n;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}


vec4 AHg(bool p2, vec3 c, vec2 dx, vec2 dy) { if (p2) return textureGrad(layers2_ah, c, dx, dy); return textureGrad(layers_ah, c, dx, dy); }
vec4 NRg(bool p2, vec3 c, vec2 dx, vec2 dy) { if (p2) return textureGrad(layers2_nr, c, dx, dy); return textureGrad(layers_nr, c, dx, dy); }
vec4 AH(bool p2, vec3 c) { if (p2) return texture(layers2_ah, c); return texture(layers_ah, c); }
vec4 NR(bool p2, vec3 c) { if (p2) return texture(layers2_nr, c); return texture(layers_nr, c); }
float TILE(bool p2, int i) { return p2 ? tile2_m[i] : tile_m[i]; }
vec3 MEAN(bool p2, int i) { return p2 ? mean2_albedo[i] : mean_albedo[i]; }

// Quilez texture repetition, technique 3 (https://iquilezles.org/articles/texturerepetition/), on an array layer.
void detiled(bool p2, vec2 uv, float layer, out vec4 ah, out vec4 nr) {
	float k = texture(variation, 0.005 * uv * 8.0).r;
	vec2 duvdx = dFdx(uv), duvdy = dFdy(uv);
	float l = k * 8.0;
	float f = fract(l);
	float ia = floor(l), ib = ia + 1.0;
	vec2 oa = sin(vec2(3.0, 7.0) * ia), ob = sin(vec2(3.0, 7.0) * ib);
	vec4 a1 = AHg(p2, vec3(uv + oa, layer), duvdx, duvdy);
	vec4 a2 = AHg(p2, vec3(uv + ob, layer), duvdx, duvdy);
	vec4 n1 = NRg(p2, vec3(uv + oa, layer), duvdx, duvdy);
	vec4 n2 = NRg(p2, vec3(uv + ob, layer), duvdx, duvdy);
	float t = smoothstep(0.2, 0.8, f - 0.1 * dot(a1.rgb - a2.rgb, vec3(1.0)));
	ah = mix(a1, a2, t);
	nr = mix(n1, n2, t);
}

// tangent-space normal (OpenGL) on a planar projection: u along `t`, v along `b`, surface normal `n`
vec3 ts_to_world(vec3 ts, vec3 t, vec3 b, vec3 n) {
	return normalize(t * ts.x * normal_strength + b * ts.y * normal_strength + n * ts.z);
}

void sample_layer(bool p2, int i, vec3 p, vec3 n, float tri, out vec3 alb, out float h, out vec3 nw, out float rough) {
	float sc = 1.0 / max(TILE(p2, i), 0.1);
	float L = float(i);
	vec4 ah, nr;
	// top projection (u = +x, v = +z; GL green = toward -v = -z)
	detiled(p2, p.xz * sc, L, ah, nr);
	vec3 nts = nr.rgb * 2.0 - 1.0;
	vec3 ny = ts_to_world(nts, vec3(1.0, 0.0, 0.0), vec3(0.0, 0.0, -1.0), n);
	if (tri > 0.001) {
		vec3 w = pow(abs(n), vec3(4.0));
		w /= (w.x + w.y + w.z);
		vec4 ahx = AH(p2, vec3(p.zy * sc, L));
		vec4 ahz = AH(p2, vec3(p.xy * sc, L));
		vec4 nrx = NR(p2, vec3(p.zy * sc, L));
		vec4 nrz = NR(p2, vec3(p.xy * sc, L));
		vec3 nx = ts_to_world(nrx.rgb * 2.0 - 1.0, vec3(0.0, 0.0, sign(n.x)), vec3(0.0, 1.0, 0.0), n);
		vec3 nz = ts_to_world(nrz.rgb * 2.0 - 1.0, vec3(-sign(n.z), 0.0, 0.0), vec3(0.0, 1.0, 0.0), n);
		vec4 aht = ahx * w.x + ah * w.y + ahz * w.z;
		vec4 nrt = nrx * w.x + nr * w.y + nrz * w.z;
		vec3 nt = normalize(nx * w.x + ny * w.y + nz * w.z);
		ah = mix(ah, aht, tri);
		nr = mix(nr, nrt, tri);
		ny = normalize(mix(ny, nt, tri));
	}
	alb = ah.rgb * albedo_scale[i];
	h = ah.a;
	nw = ny;
	rough = clamp(mix(rough_floor, 1.0, nr.a) * rough_scale[i], 0.04, 1.0);   // ground is matte: scans' roughness kept as variation above a floor
}


float hash21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }

void detiled_p(vec2 uv, float layer, out vec4 ah, out vec4 nr) {
	float k = texture(variation, 0.04 * uv).r;
	vec2 duvdx = dFdx(uv), duvdy = dFdy(uv);
	float l = k * 8.0;
	float f = fract(l);
	float ia = floor(l), ib = ia + 1.0;
	vec2 oa = sin(vec2(3.0, 7.0) * ia), ob = sin(vec2(3.0, 7.0) * ib);
	vec4 a1 = textureGrad(paved_ah, vec3(uv + oa, layer), duvdx, duvdy);
	vec4 a2 = textureGrad(paved_ah, vec3(uv + ob, layer), duvdx, duvdy);
	vec4 n1 = textureGrad(paved_nr, vec3(uv + oa, layer), duvdx, duvdy);
	vec4 n2 = textureGrad(paved_nr, vec3(uv + ob, layer), duvdx, duvdy);
	float t = smoothstep(0.2, 0.8, f - 0.1 * dot(a1.rgb - a2.rgb, vec3(1.0)));
	ah = mix(a1, a2, t);
	nr = mix(n1, n2, t);
}

// concrete apron: laid slabs with joints, per-slab value, patch repairs, cracks, stains
void concrete(vec3 p, vec3 n, float cam_d, out vec3 alb, out vec3 nw, out float rough) {
	vec4 ah, nr;
	detiled_p(p.xz / paved_tile_m[0], 0.0, ah, nr);
	vec2 sp = p.xz / slab_m;
	vec2 id = floor(sp);
	vec2 f = fract(sp);
	float h1 = hash21(id), h2 = hash21(id + 17.3), h3 = hash21(id + 51.7);
	alb = ah.rgb * (0.9 + 0.18 * h1);
	rough = clamp(mix(0.75, 1.0, nr.a), 0.6, 1.0);
	vec3 nts = nr.rgb * 2.0 - 1.0;
	nw = normalize(vec3(1.0, 0.0, 0.0) * nts.x * 0.6 + vec3(0.0, 0.0, -1.0) * nts.y * 0.6 + n * nts.z);
	// patch repair: a darker, smoother inset rectangle in some slabs
	vec2 pc = vec2(0.2 + 0.4 * h2, 0.2 + 0.4 * h3), ps = vec2(0.15 + 0.25 * h3, 0.12 + 0.3 * h1);
	float patch_ = step(h2, 0.14) * step(abs(f.x - pc.x), ps.x) * step(abs(f.y - pc.y), ps.y);
	alb = mix(alb, alb * vec3(0.78, 0.78, 0.8), patch_);
	rough = mix(rough, 0.7, patch_);
	// cracks: thin noise ridges in a third of the slabs
	float cn = texture(variation, p.xz / 26.0 + id * 0.37).r;
	float cw_ = fwidth(cn) * 0.9 + 0.0015;
	float crack = (1.0 - smoothstep(0.0, cw_, abs(cn - 0.5))) * step(h3, 0.18) * (1.0 - smoothstep(80.0, 200.0, cam_d));
	alb *= 1.0 - 0.35 * crack;
	// stains: broad soft dark blotches (oil, water)
	float st = smoothstep(0.62, 0.8, texture(variation, p.xz / 23.0 + 0.6).r);
	alb *= 1.0 - 0.22 * st;
	// joints
	float jd = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y)) * slab_m;
	float fw = fwidth(jd) + 0.005;
	float joint = 1.0 - smoothstep(0.025, 0.025 + fw, jd);
	alb *= 1.0 - 0.5 * joint;
}

void ground(bool p2, int ka, int kb, float wb, vec3 n, float tri, float dist, float far,
		out vec3 alb, out vec3 nw, out float rough) {
	rough = 0.9;
	if (far < 0.999) {
		vec3 aa, ab, na, nb; float ha, hb, ra, rb;
		sample_layer(p2, ka, world_pos, n, tri, aa, ha, na, ra);
		if (wb > 0.01) {
			sample_layer(p2, kb, world_pos, n, tri, ab, hb, nb, rb);
		} else {
			ab = aa; hb = 0.0; nb = na; rb = ra;
		}
		// height blend
		float x = ha + (1.0 - wb);
		float y = hb + wb;
		float m = max(x, y) - blend_depth;
		float u = max(x - m, 0.0), v = max(y - m, 0.0);
		float t = v / max(u + v, 1e-4);
		alb = mix(aa, ab, t);
		nw = normalize(mix(na, nb, t));
		rough = mix(ra, rb, t);
		vec3 fa = mix(MEAN(p2, ka) * albedo_scale[ka], MEAN(p2, kb) * albedo_scale[kb], t);
		alb = mix(alb, fa, far);
		nw = normalize(mix(nw, n, far));
		wb = t;
	} else {
		alb = mix(MEAN(p2, ka) * albedo_scale[ka], MEAN(p2, kb) * albedo_scale[kb], wb);
		nw = n;
		rough = mix(rough_scale[ka], rough_scale[kb], wb) * 0.8;
	}
	// macro variation: each layer again at macro_ratio x its tile, as value and colour drift around its own mean
	// (patches, wear, worn ground) so a field reads varied from 300-600 m instead of one mipped colour
	{
		vec3 ma = AH(p2, vec3(world_pos.xz / (TILE(p2, ka) * macro_ratio), float(ka))).rgb / max(MEAN(p2, ka), vec3(0.01));
		vec3 mb = AH(p2, vec3(world_pos.zx / (TILE(p2, kb) * macro_ratio * 1.3) + 0.31, float(kb))).rgb / max(MEAN(p2, kb), vec3(0.01));
		vec3 mf = clamp(mix(ma, mb, wb), vec3(0.45), vec3(1.8));
		float mw = mix(macro_near, 1.0, smoothstep(60.0, macro_far_m, dist));
		alb *= mix(vec3(1.0), mf, mw);
	}
}

void fragment() {
	vec2 suv = UV;   // the ground mesh's UV covers the map 0..1 (row 0 = north), like the splat
	vec2 wn = vec2(texture(variation, world_pos.xz / 37.0).r, texture(variation, world_pos.zx / 41.0 + 0.37).r) - 0.5;
	vec2 wn2 = vec2(texture(variation, world_pos.xz / 9.0 + 0.71).r, texture(variation, world_pos.zx / 11.0 + 0.13).r) - 0.5;
	vec2 wuv = suv + (wn * 2.0 * warp_m + wn2 * 2.0 * warp_m / 3.5) / map_side_m;   // borders wander, ragged at two scales
	// bilinear class weights from the 4 nearest splat texels
	vec2 sp = wuv * splat_px - 0.5;
	vec2 f = fract(sp);
	ivec2 b0 = ivec2(floor(sp));
	float cw[8] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
	float wear = 0.0;
	ivec2 mx = ivec2(int(splat_px) - 1);
	for (int j = 0; j < 4; j++) {
		ivec2 o = ivec2(j & 1, j >> 1);
		vec4 s = texelFetch(splat, clamp(b0 + o, ivec2(0), mx), 0);
		float wt = (o.x == 1 ? f.x : 1.0 - f.x) * (o.y == 1 ? f.y : 1.0 - f.y);
		int c1 = int(s.r * 255.0 + 0.5), c2 = int(s.g * 255.0 + 0.5);
		float bl = s.b * 0.5;   // B = 255: an even mix
		cw[clamp(c1, 0, 7)] += wt * (1.0 - bl);
		cw[clamp(c2, 0, 7)] += wt * bl;
		wear += wt * s.a;
	}
	int ka = 0, kb = 1;
	if (cw[kb] > cw[ka]) { ka = 1; kb = 0; }
	for (int i = 2; i < 8; i++) {
		if (cw[i] > cw[ka]) { kb = ka; ka = i; }
		else if (cw[i] > cw[kb]) { kb = i; }
	}
	float wb = cw[kb] / max(cw[ka] + cw[kb], 1e-4);

	vec3 n = normalize(world_n);
	vec3 n_flat = n;   // paving ignores the recovered relief (it was painted under the old cement tiles)
	float rao = 1.0;
	if (has_relief) {
		vec4 rl4 = texture(relief, suv); vec3 rl = rl4.rgb;
		vec2 mn = (rl.rg * 2.0 - 1.0) * relief_strength;
		if (has_ripple) {
			float rf = 1.0 - smoothstep(ripple_fade_start, ripple_fade_end, length(world_pos - CAMERA_POSITION_WORLD));
			mn += (texture(ripple, suv).rg * 2.0 - 1.0) * relief_strength * rf;
		}
		vec3 nm = normalize(n + vec3(mn.x, 0.0, mn.y) * n.y);   // the macro slope on top of the mesh's own
		vec3 sl = normalize(sun_dir);
		float rel = max(dot(nm, sl), 0.0) / max(dot(n, sl), 0.15);
		rao = mix(1.0, rl.b, ao_strength) * mix(1.0, clamp(rel, 0.35, 1.6), relief_shade) * (1.0 + clamp((rl4.a - 0.5) * 2.0, -1.0, 1.0) * curvature_shade);
		n = nm;
	}
	float tri = 1.0 - smoothstep(tri_start, tri_end, n.y);
	float dist = length(world_pos - CAMERA_POSITION_WORLD);
	float far = smoothstep(far_start, far_end, dist);
	vec3 alb; vec3 nw; float rough;
	ground(false, ka, kb, wb, n, tri, dist, far, alb, nw, rough);
	vec3 alb2 = vec3(0.0); vec3 nw2 = n; float r2 = 1.0;
	vec2 m2rg = vec2(0.0);
	if (has_p2) {
		m2rg = texture(mask2, suv).rg;
		if (max(m2rg.r, m2rg.g) > 0.004) {
			ground(true, ka, kb, wb, n, tri, dist, far, alb2, nw2, r2);
			float m2 = mask2_edge > 0.0 ? smoothstep(0.5 - mask2_edge, 0.5 + mask2_edge, m2rg.r) : m2rg.r;
			alb = mix(alb, alb2, m2); nw = normalize(mix(nw, nw2, m2)); rough = mix(rough, r2, m2);
		}
	}
	float v1 = texture(variation, world_pos.xz / 140.0).r, v2 = texture(variation, world_pos.xz / 47.0 + 0.5).r;
	float v3 = texture(variation, world_pos.zx / 17.0 + 0.2).r;
	float vv = (v1 - 0.5) * 0.55 + (v2 - 0.5) * 0.3 + (v3 - 0.5) * 0.15;
	alb *= 1.0 + macro_var * vv * 2.0;
	// worn patches: darker, browner, less saturated ground in broad noise valleys
	float worn = smoothstep(0.58, 0.72, texture(variation, world_pos.xz / 63.0 + 0.9).r);
	alb = mix(alb, vec3(dot(alb, vec3(0.3, 0.55, 0.15))) * vec3(1.04, 0.98, 0.9) * 0.88, worn * 0.3);
	// wear (splat A): darker, browner compacted ground around roads and bases, worn tracks, erosion channels
	float wr = wear * (0.75 + 0.5 * texture(variation, world_pos.xz / 13.0 + 0.4).r);
	alb = mix(alb, vec3(dot(alb, vec3(0.3, 0.55, 0.15))) * vec3(1.02, 0.97, 0.9) * 0.85, clamp(wr, 0.0, 1.0) * wear_strength * 0.7);
	rough = mix(rough, 0.95, wr * 0.5);
	// pale dusty patches: lighter, greyer ground in broad noise peaks
	float dusty = smoothstep(0.6, 0.74, texture(variation, world_pos.zx / 81.0 + 0.27).r) * (1.0 - wr) * (1.0 - m2rg.r);   // not on snow: the lighter, greyer patches read as a glowing haze on a snowfield (mc2_19)
	alb = mix(alb, vec3(dot(alb, vec3(0.3, 0.55, 0.15))) * vec3(1.0, 0.98, 0.95) * 1.28, dusty * dusty_strength);
	alb *= rao * albedo_gain;   // relief AO and the map's value on the ground only, before paving is laid over it
	vec3 tn = texture(tint, suv).rgb * 2.0;   // relative to the map's mean: 1.0 = no change
	tn = mix(tn, vec3(dot(tn, vec3(0.3, 0.55, 0.15))), clamp(m2rg.r * snow_tint_neutral, 0.0, 1.0));
	alb *= mix(vec3(1.0), tn, tint_strength);
	// overlays and cement, as terrain.gdshader
	if (paved_v3 && apron_on) {
		float d = (texture(apron_sdf, suv).r - 128.0 / 255.0) * (255.0 / 127.0) * apron_spread;
		if (d > -3.0) {
			float e = 1.0 / map_side_m;
			float dx = (texture(apron_sdf, suv + vec2(e, 0.0)).r - texture(apron_sdf, suv - vec2(e, 0.0)).r);
			float dz = (texture(apron_sdf, suv + vec2(0.0, e)).r - texture(apron_sdf, suv - vec2(0.0, e)).r);
			vec2 outdir = -normalize(vec2(dx, dz) + 1e-6);   // world x, z (uv v runs with +z)
			float fw = fwidth(d) + 0.02;
			float w = smoothstep(-fw, fw, d);
			vec3 ca; vec3 cn; float cr;
			concrete(world_pos, n_flat, dist, ca, cn, cr);
			// kerb: a 0.55 m raised edge strip, lighter, with a dark joint on its inner side
			float kerb = smoothstep(0.0, 0.05, d) * (1.0 - smoothstep(0.5, 0.56, d));
			float kjoint = smoothstep(0.53, 0.56, d) * (1.0 - smoothstep(0.6, 0.65, d));
			ca = mix(ca, ca * 1.32 + 0.05, kerb * kerb_strength);
			ca *= 1.0 - 0.45 * kjoint;
			float face = 1.0 - smoothstep(0.0, 0.1, d);
			cn = normalize(cn + vec3(outdir.x, 0.0, outdir.y) * (face * 0.9 - kjoint * 0.4));
			// dirt side: a dark 0.3 m gutter, then soft grime over ~2 m
			float o = -d;
			alb = mix(alb, alb * vec3(0.55, 0.53, 0.5), (1.0 - smoothstep(0.0, 0.3, o)) * step(0.0, o) * 0.9);
			alb = mix(alb, alb * vec3(0.8, 0.78, 0.74), (1.0 - smoothstep(0.3, 2.2, o)) * step(0.0, o) * 0.7);
			alb = mix(alb, ca, w);
			rough = mix(rough, cr, w);
			nw = normalize(mix(nw, cn, w));
			if (m2rg.g > 0.004) {   // snow drifted onto the paving edge in irregular tongues (mask2 G = snow beside it)
				float dn = (texture(variation, world_pos.xz / 9.0 + 0.61).r - 0.5) * 7.0 + (texture(variation, world_pos.zx / 3.1).r - 0.5) * 2.0;
				float sd = m2rg.g * (1.0 - smoothstep(0.0, 2.5, d - 1.5 * m2rg.g + dn)) * w;
				alb = mix(alb, alb2 * rao * albedo_gain, sd * 0.92); rough = mix(rough, r2, sd); nw = normalize(mix(nw, nw2, sd));
			}
		}
	}
	if (vertices_per_side > 0.0) {
		vec2 qf = suv * vertices_per_side;
		ivec2 q = clamp(ivec2(floor(qf)), ivec2(0), ivec2(int(vertices_per_side) - 1));
		vec2 local = fract(qf);
		vec2 cells = texelFetch(overlay_index, q, 0).rg;
		float cell_px = atlas_tile + 2.0 * atlas_pad;
		vec2 atlas_px = vec2(atlas_cols * cell_px);
		vec2 dl_dx = dFdx(qf) * atlas_tile / atlas_px;
		vec2 dl_dy = dFdy(qf) * atlas_tile / atlas_px;
		if (cells.g > 0.5) {
			float wraw = texture(cement_weight, (qf + 0.5) / vertices_per_side).r;
			if (paved_v3 && apron_on) {
				// drawn from apron_sdf below
			} else {
				float c = cells.g - 1.0;
				vec2 org = vec2(mod(c, atlas_cols), floor(c / atlas_cols)) * cell_px + atlas_pad;
				vec3 cem = textureGrad(overlay_atlas, (org + local * atlas_tile) / atlas_px, dl_dx, dl_dy).rgb;
				float w = smoothstep(0.3, 0.9, wraw);
				alb = mix(alb, cem, w);
				rough = mix(rough, 0.85, w);
				nw = normalize(mix(nw, n_flat, w));
			}
		}
		if (cells.r > 0.5) {
			float c = cells.r - 1.0;
			vec2 org = vec2(mod(c, atlas_cols), floor(c / atlas_cols)) * cell_px + atlas_pad;
			vec2 auv = (org + local * atlas_tile) / atlas_px;
			if (paved_v3 && mk_cols > 0.0) {
				float mc = texelFetch(markings_index, q, 0).r - 1.0;
				if (mc >= 0.0) {
					float mcell = mk_tile + 2.0 * mk_pad;
					vec2 mpx = vec2(mk_cols * mcell);
					vec2 morg = vec2(mod(mc, mk_cols), floor(mc / mk_cols)) * mcell + mk_pad;
					vec2 muv = (morg + local * mk_tile) / mpx;
					vec2 mdx = dFdx(qf) * mk_tile / mpx, mdy = dFdy(qf) * mk_tile / mpx;
					vec4 mk = textureGrad(markings, muv, mdx, mdy);
					vec3 sd = (mk.rgb - 128.0 / 255.0) * (255.0 / 127.0) * mk_spread;   // metres, + inside
					// gravel/dirt tracks
					vec4 tah, tnr;
					detiled_p(world_pos.xz / paved_tile_m[2], 2.0, tah, tnr);
					float ta = mk.a * (0.8 + 0.4 * texture(variation, world_pos.xz / 5.0).r);
					// dirt/gravel track: the biome's own ground (already scaled by the map's gain) lifted a little for compaction and warmed,
					// with the gravel layer's detail only as a value variation. The raw ambientCG gravel was a pale grey ribbon, un-darkened by the gain.
					float tdet = clamp(dot(tah.rgb, vec3(0.3, 0.55, 0.15)) / 0.22, 0.55, 1.6);
					vec3 tcol = alb * vec3(3.3, 2.8, 2.1) * (0.62 + 0.38 * tdet);   // compacted dry earth reads about 3x the ground's value, warm: the original's tracks are clearly lighter than their surround
					tcol *= mix(1.0, 0.62, smoothstep(0.12, 0.35, dot(alb, vec3(0.3, 0.55, 0.15))));   // on snow a track is darker than its surround
					alb = mix(alb, tcol, clamp(ta, 0.0, 1.0));
					rough = mix(rough, 0.95, ta);
					// asphalt
					vec4 aah, anr;
					detiled_p(world_pos.xz / paved_tile_m[1], 1.0, aah, anr);
					float wearn = texture(variation, world_pos.xz / 17.0 + 0.3).r;
					vec3 asph = aah.rgb * 0.55 * (0.88 + 0.24 * wearn);
					float aw = fwidth(sd.b) + 0.02;
					float ar = smoothstep(-aw, aw, sd.b);
					// paint: crisp SDF edges, slightly worn (a soft fade and a few thin gaps, never blobs)
					float ww = fwidth(sd.r) * 0.7 + 0.004, yw = fwidth(sd.g) * 0.7 + 0.004;
					float mw = smoothstep(-ww, ww, sd.r), my = smoothstep(-yw, yw, sd.g);
					float pw = 0.82 + 0.18 * texture(variation, world_pos.xz / 3.7).r;
					float gap = smoothstep(0.78, 0.86, texture(variation, world_pos.xz / 1.9 + 0.4).r);
					pw *= 1.0 - 0.6 * gap;
					asph = mix(asph, vec3(0.80), mw * pw);
					asph = mix(asph, vec3(0.74, 0.58, 0.16), my * pw);
					alb = mix(alb, asph, ar);
					rough = mix(rough, mix(clamp(mix(0.65, 0.95, anr.a), 0.5, 1.0), 0.72, max(mw, my) * pw), ar);
					vec3 ats = anr.rgb * 2.0 - 1.0;
					vec3 an = normalize(vec3(1.0, 0.0, 0.0) * ats.x * 0.5 + vec3(0.0, 0.0, -1.0) * ats.y * 0.5 + n_flat * ats.z);
					nw = normalize(mix(nw, an, ar));
				}
			} else {
				vec4 ov = textureGrad(overlay_atlas, auv, dl_dx, dl_dy);
				alb = mix(alb, ov.rgb, ov.a);
				rough = mix(rough, 0.8, ov.a);
				nw = normalize(mix(nw, n_flat, ov.a));
			}
		}
	}
	if (debug_view == 1) alb = mix(DEBUG_RGB[ka], DEBUG_RGB[kb], wb);
	if (debug_view == 2) alb = vec3(wb);
	if (debug_view == 3) alb = tn * 0.5;
	if (debug_view == 4) alb = vec3(far);
	ALBEDO = alb;
	EMISSION = alb * shadow_fill;
	ROUGHNESS = rough;
	SPECULAR = specular;
	METALLIC = 0.0;
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
