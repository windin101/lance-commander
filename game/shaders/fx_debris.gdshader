// Debris chunks from the EffectsView pool (I87): lit, opaque, scorched; glow-hot for the first moments.
shader_type spatial;
render_mode cull_disabled;

varying float v_t;
varying vec4 v_col;

void vertex() {
	v_t = clamp(INSTANCE_CUSTOM.x / max(INSTANCE_CUSTOM.y, 0.001), 0.0, 1.0);
	v_col = COLOR;
	// shrink away at the end instead of popping
	VERTEX *= 1.0 - smoothstep(0.8, 1.0, v_t);
}

void fragment() {
	ALBEDO = v_col.rgb;
	ROUGHNESS = 0.9;
	METALLIC = 0.2;
	EMISSION = vec3(1.0, 0.45, 0.12) * 3.0 * (1.0 - smoothstep(0.0, 0.25, v_t));
}
