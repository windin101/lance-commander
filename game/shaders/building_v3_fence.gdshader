shader_type spatial;
// v3 chain-link and mesh panels (LANCE-21 walls and fences): the project chain texture on a flat panel, alpha blended, seen from both sides.
// The wire fades toward a constant translucency with distance so a fence still reads as a faint lattice at RTS range instead of vanishing.
render_mode blend_mix, depth_draw_never, cull_disabled, specular_schlick_ggx;

uniform sampler2D ar_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float tile_m = 1.2;
uniform vec3 tint : source_color = vec3(1.0);
uniform float fade_near = 40.0;
uniform float fade_far = 160.0;
uniform float scorch : hint_range(0.0, 1.0) = 0.0;

varying float vburn;
varying float vao;
varying float dist;

void vertex() {
	vburn = COLOR.b;
	vao = COLOR.a;
	dist = length((MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz);
}

void fragment() {
	vec4 t = texture(ar_tex, UV / tile_m);
	float burn = clamp(max(vburn, scorch), 0.0, 1.0);
	float k = smoothstep(fade_near, fade_far, dist);
	ALBEDO = mix(t.rgb * tint * vao, vec3(0.03), burn * 0.6);
	ALPHA = mix(t.a, 0.62, k);
	METALLIC = 0.35;
	ROUGHNESS = 0.55;
	SPECULAR = 0.5;
}
