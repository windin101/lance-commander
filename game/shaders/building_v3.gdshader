shader_type spatial;
// v3 buildings (LANCE-21, tools/art/v3/bld_*.py): one ShaderMaterial per surface of a procedural model, all sharing this
// shader. The model's UV0 is in metres, so a library material tiles at its own physical size (tile_m); no per-model textures.
//   mode 0  library material: albedo+roughness (_ar), normal RG + metal B + AO A (_nm), two rotated samples to break tiling
//   mode 1  trim sheet: 8 bands of 4 x 0.5 m, band in UV2.x, pattern repeats in both directions (see bld_trim.py)
//   (decals are building_v3_decal.gdshader: a transparent shader cannot share this opaque one)
//   mode 3  burnt interior: the rust set, darkened and sooted
// Vertex colour: R faction tint mask, G extra wear, B scorch. Environment: the mission's dust and snow (MechPaint.env_*).
render_mode depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D ar_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D nm_tex : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grunge_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform int mode = 0;
uniform float tile_m = 2.0;
uniform float lined = 0.0;   // 1: a ribbed sheet (corrugated): ribs run vertically, and no rotated second sample (it would moire)
uniform float metal_k = 1.0;
uniform float normal_depth = 1.0;
uniform vec3 base_tint : source_color = vec3(1.0);
uniform vec3 tint : source_color = vec3(0.86, 0.66, 0.1);
uniform float tint_amount = 1.0;
uniform float wear = 1.0;
uniform float desat = 0.0;        // pulls a tinted scan (blue galvanising) toward grey
uniform float contrast = 1.0;   // pulls a high-contrast scan (chipped paint) toward its mean for an intact look
uniform float dust : hint_range(0.0, 1.0) = 0.2;
uniform float snow : hint_range(0.0, 1.0) = 0.0;
uniform vec3 dust_colour : source_color = vec3(0.56, 0.5, 0.4);
uniform float scorch : hint_range(0.0, 1.0) = 0.0;   // whole-model burn (a destroyed state), on top of the vertex burn

varying vec3 mpos;
varying vec3 mnrm;
varying vec4 vcol;
varying vec2 vband;

void vertex() {
	mpos = VERTEX;
	mnrm = NORMAL;
	vcol = COLOR;
	vband = UV2;
}

vec3 cotangent_normal(vec3 n_view, vec3 p_view, vec2 uv, vec3 nm) {
	vec3 dp1 = dFdx(p_view);
	vec3 dp2 = dFdy(p_view);
	vec2 duv1 = dFdx(uv);
	vec2 duv2 = dFdy(uv);
	vec3 dp2perp = cross(dp2, n_view);
	vec3 dp1perp = cross(n_view, dp1);
	vec3 T = dp2perp * duv1.x + dp1perp * duv2.x;
	vec3 B = -(dp2perp * duv1.y + dp1perp * duv2.y);   // glTF v runs down, OpenGL normal maps' green runs up
	float inv = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-12));
	return normalize(mat3(T * inv, B * inv, n_view) * nm);
}

vec3 unpack_n(vec2 rg) {
	vec2 xy = rg * 2.0 - 1.0;
	return vec3(xy, sqrt(max(0.0, 1.0 - dot(xy, xy))));
}

void fragment() {
	vec4 ar;
	vec4 nm;
	vec2 uv;
	float rough_k = 1.0;
	if (mode == 1) {
		vec2 g = vec2(1.0 / 4.0, 1.0 / (0.5 * 8.0));
		uv = vec2(UV.x / 4.0, (vband.x + clamp(fract(UV.y / 0.5), 0.012, 0.988)) / 8.0);
		ar = textureGrad(ar_tex, uv, dFdx(UV) * g, dFdy(UV) * g);
		nm = textureGrad(nm_tex, uv, dFdx(UV) * g, dFdy(UV) * g);
	} else {
		uv = UV / tile_m;
		if (lined > 0.5) {
			uv = uv.yx;
		}
		vec2 uv2 = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * uv * 0.37 + vec2(0.31, 0.57);
		float bn = texture(grunge_tex, mpos.xz * 0.05 + mpos.y * 0.03).g;
		float k = smoothstep(0.35, 0.65, bn);
		vec4 a1 = texture(ar_tex, uv);
		vec4 a2 = texture(ar_tex, uv2);
		vec4 n1 = texture(nm_tex, uv);
		vec4 n2 = texture(nm_tex, uv2);
		float kk = k * 0.55 * (1.0 - lined);
		ar = mix(a1, a2, kk);
		nm = mix(n1, n2, kk);
	}
	float g1 = texture(grunge_tex, mpos.xz * 0.21 + mpos.y * 0.13).g;
	float g2 = texture(grunge_tex, mpos.xy * 0.4 + mpos.zy * 0.4).r;
	vec3 col = ar.rgb;
	float rough = ar.a;
	float metal = nm.b * metal_k;
	float ao = nm.a;
	vec3 n_ts = unpack_n(nm.rg);
	n_ts = normalize(mix(vec3(0.0, 0.0, 1.0), n_ts, normal_depth));

	if (mode == 0) {
		col = mix(col, vec3(dot(col, vec3(0.333))), desat);
		col = mix(vec3(0.78), col, contrast);
		col *= base_tint;
		// faction tint where the mesh marks it
		float tm = vcol.r * tint_amount;
		col = mix(col, tint * (0.3 + 0.7 * dot(col, vec3(0.333))), tm);
		// grime: dirt climbing from the ground, run-off streaks, baked run-off below ledges (vertex G) and baked AO (vertex A)
		float ground = 1.0 - smoothstep(0.0, 9.0, mpos.y);
		float ang = atan(mpos.z, mpos.x);
		float streak = smoothstep(0.4, 0.8, texture(grunge_tex, vec2(ang * 3.0, mpos.y * 0.03)).g);
		float g = wear * (0.25 * g1 + 0.65 * ground * (0.45 + g2)) + vcol.g * (0.4 + 0.6 * streak) + (1.0 - vcol.a) * 0.55 + (1.0 - ao) * 0.4;
		g = clamp(g, 0.0, 0.92);
		col *= 0.62 + 0.7 * g1;                                   // macro value breakup
		col = mix(col, col * vec3(0.30, 0.26, 0.21), g);
		rough = clamp(rough + g * 0.25, 0.05, 1.0);
	} else if (mode == 1) {
		float tm = vcol.r * tint_amount;
		col = mix(col, tint * (0.3 + 0.7 * dot(col, vec3(0.333))), tm);
		col = mix(col, col * vec3(0.4, 0.36, 0.32), clamp(wear * 0.5 * g1 + (1.0 - ao) * 0.35, 0.0, 0.7));
		col *= mix(1.0, vcol.a, 0.8);
		col = mix(col, col * vec3(0.4, 0.34, 0.28), vcol.g * 0.6);
	} else if (mode == 3) {
		col = col * vec3(0.62, 0.45, 0.34) * (0.55 + g1);
		rough = 0.65;
	}

	{
		float up = clamp(normalize(mnrm).y, 0.0, 1.0);
		float low2 = 1.0 - smoothstep(0.0, 2.0, mpos.y);
		float dm = clamp(dust * (smoothstep(0.25, 0.9, up) * 0.7 + low2 * 0.6) * (0.55 + 0.9 * g1) * (1.0 - vcol.b), 0.0, 1.0);
		col = mix(col, dust_colour * (0.85 + 0.3 * g2), dm * 0.75);
		float sm = clamp(snow * smoothstep(0.45, 0.8, up + (g1 - 0.5) * 0.3) * 1.6, 0.0, 1.0);
		col = mix(col, vec3(0.88, 0.9, 0.93), sm);
		rough = mix(rough + dm * 0.3, 0.75, sm);
		float burn = clamp(max(vcol.b, scorch) * (0.65 + 0.7 * g1), 0.0, 1.0);
		col = mix(col, vec3(0.035, 0.03, 0.028) * (0.6 + 0.8 * g2), burn * 0.9);
		rough = mix(rough, 0.8, burn);
		metal *= (1.0 - dm) * (1.0 - burn);
		ALBEDO = col;
		METALLIC = metal;
		ROUGHNESS = clamp(rough, 0.04, 1.0);
		SPECULAR = 0.5;
		NORMAL = cotangent_normal(NORMAL, VERTEX, uv, n_ts);
		AO = ao * mix(1.0, vcol.a, 0.85);
		AO_LIGHT_AFFECT = 0.6;
	}
}
