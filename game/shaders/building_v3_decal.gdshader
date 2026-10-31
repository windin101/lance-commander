shader_type spatial;
// v3 building decals (LANCE-21): the project decal atlas (tools/art/v3/bld_trim.py) on thin offset geometry, alpha blended.
render_mode blend_mix, depth_draw_never, cull_disabled, specular_schlick_ggx;

uniform sampler2D ar_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform float scorch : hint_range(0.0, 1.0) = 0.0;

varying float vburn;

void vertex() {
	vburn = COLOR.b;
}

void fragment() {
	vec4 c = texture(ar_tex, UV);
	float burn = clamp(max(vburn, scorch), 0.0, 1.0);
	ALBEDO = mix(c.rgb, vec3(0.03), burn * 0.5);
	ALPHA = c.a;
	ROUGHNESS = 0.8;
	SPECULAR = 0.35;
}
