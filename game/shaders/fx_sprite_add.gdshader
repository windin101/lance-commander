// Additive glowing particles: flashes, sparks, fire (I87).
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;
#include "res://shaders/fx_sprite.gdshaderinc"

void fragment() {
	vec4 t = texture(tex, v_uv);
	vec3 c;
	float a = t.a;
	if (use_ramp) {
		float i = clamp(t.r * (1.0 - cool * v_t), 0.0, 1.0);
		c = texture(ramp, vec2(i, 0.5)).rgb * v_col.rgb;
		a *= smoothstep(0.02, 0.25, i);
	} else {
		c = t.rgb * v_col.rgb;
	}
	ALBEDO = c * energy;
	ALPHA = clamp(a * v_col.a * fx_alpha(SCREEN_UV, VERTEX, INV_PROJECTION_MATRIX), 0.0, 1.0);
}
