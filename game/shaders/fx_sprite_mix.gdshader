// Lit, alpha-blended particles: smoke, dust, splash (I87). Lit by the scene so night maps stay dark.
shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_never, shadows_disabled, specular_disabled;
#include "res://shaders/fx_sprite.gdshaderinc"

void fragment() {
	vec4 t = texture(tex, v_uv);
	ALBEDO = t.rgb * v_col.rgb;
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
	BACKLIGHT = vec3(0.35);
	ALPHA = clamp(t.a * v_col.a * fx_alpha(SCREEN_UV, VERTEX, INV_PROJECTION_MATRIX), 0.0, 1.0);
}
