shader_type spatial;
render_mode cull_disabled, specular_disabled, depth_draw_opaque;
// Understorey plants (terrain polish round 3, 2026-11-01; tools/art/terrain/plants_atlas.py): ferns, wildflowers, bushes,
// hedges and dry scrub, all cut out of one 2 x 2 atlas (0 fern, 1 wildflowers, 2 leaf mass, 3 dry scrub). A mesh names its
// cell in UV2.x; UV2.y > 1.5 tiles the cell (the leaf-mass domes of bushes and hedges), else the cell is used once (cards).
// COLOR is the per-instance tint (the map palette's own greens, the albedo gain applied by the dress). Wind sways the top
// of the plant; cards get an up-bent normal (up_mix) and domes keep their own so they read as soft volumes. Alpha-cut
// with the cut raised by mip level so distant plants keep their mass; the dress fades them out with a visibility range.

uniform sampler2D atlas : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float wind = 0.45;
uniform float alpha_cut = 0.42;
uniform float up_mix = 0.7;
uniform float far_fade_start = 1.0e6;   // flowers lose their colour toward the ground tone with distance
uniform float far_fade_end = 2.0e6;
uniform float fill_tint = 0.6;   // how much of the instance tint the floor adds on top of the albedo (per map plant_fill_tint: 0 where the ground is so dark the tint reads as pale mint discs)
uniform float fill = 0.0;   // the ground's own shadow_fill: a floor of the plant's colour on night and airless maps

varying vec3 vn;
varying float h_k;
varying float far_k;
varying float cell_id;
varying float tile_rep;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	h_k = clamp(VERTEX.y / 0.9, 0.0, 1.0);
	float gust = sin(TIME * 1.2 + dot(origin.xz, vec2(0.1, 0.07))) * 0.6 + sin(TIME * 2.7 + origin.x * 0.29) * 0.25;
	VERTEX.x += gust * wind * h_k * h_k * 0.12;
	VERTEX.z += cos(TIME * 1.0 + origin.z * 0.08) * wind * h_k * h_k * 0.07;
	vn = normalize((MODELVIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	far_k = smoothstep(far_fade_start, far_fade_end, length(origin - CAMERA_POSITION_WORLD));
	cell_id = UV2.x;
	tile_rep = UV2.y;
}

void fragment() {
	vec2 uv = UV;
	vec2 g = vec2(1.0);
	if (tile_rep > 1.5) {
		uv = fract(UV * tile_rep);
		g = vec2(tile_rep);
	} else {
		uv = clamp(UV, vec2(0.003), vec2(0.997));
	}
	vec2 org = vec2(mod(cell_id, 2.0), floor(cell_id * 0.5)) * 0.5;
	vec2 duv = org + uv * 0.5;
	vec4 t = textureGrad(atlas, duv, dFdx(UV) * g * 0.5, dFdy(UV) * g * 0.5);
	vec2 px = UV * g * vec2(textureSize(atlas, 0)) * 0.5;
	float lod = max(0.0, log2(max(length(dFdx(px)), length(dFdy(px)))));
	ALPHA = clamp(t.a * (1.0 + lod * 0.4), 0.0, 1.0);
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	vec3 up = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	NORMAL = normalize(mix(vn, up, up_mix));
	vec3 a = t.rgb * COLOR.rgb * (0.62 + 0.38 * h_k);
	ALBEDO = mix(a, COLOR.rgb * 0.3, far_k * 0.7);
	ROUGHNESS = 1.0;
	BACKLIGHT = ALBEDO * 0.3;
	EMISSION = (ALBEDO + COLOR.rgb * fill_tint) * fill;
}
