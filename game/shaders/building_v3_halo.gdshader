// Beacon / runway-lamp halo (LANCE spaceport family, tools/art/v3/bld_spaceport.py): one additive camera-facing quad per lamp, soft radial falloff.
// The mesh holds four near-coincident vertices at the lamp, UV0 = the corner (0..1); the corner is pushed out in view space here, so the halo keeps
// its size on screen terms (size in metres) from any camera. `strength` is dim by day and full at night (BuildingV3.set_night).
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, fog_disabled;

uniform vec3 col : source_color = vec3(1.0, 0.2, 0.15);
uniform float strength = 0.12;
uniform float size = 3.2;
varying vec2 q;

void vertex() {
	q = UV * 2.0 - 1.0;
	vec4 c = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	c.xy += q * size * 0.5;
	POSITION = PROJECTION_MATRIX * c;
}

void fragment() {
	float d = length(q);
	float a = clamp(1.0 - d, 0.0, 1.0);
	float core = a * a * a;
	ALBEDO = col * strength * (core * 2.5 + a * 0.25);
	ALPHA = 1.0;
}
