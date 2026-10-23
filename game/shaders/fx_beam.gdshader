// Beams, tracers, missile bodies and lightning for EffectsView (I87). The mesh is a strip with x in [-1, 1]
// across and y in [0, 1] along; the node's origin is the tail, its Y axis spans to the head. The strip turns to
// face the camera and never gets thinner than min_px pixels, so beams read at every RTS zoom.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

instance uniform vec4 core_color : source_color = vec4(1.0);
instance uniform vec4 glow_color : source_color = vec4(1.0, 0.2, 0.1, 1.0);
instance uniform float width = 0.5;       // glow half-width, m
instance uniform float core = 0.3;        // core half-width as a fraction of the glow
instance uniform float intensity = 1.0;   // 0..1 fade
instance uniform float jitter = 0.0;      // lightning: sideways displacement, m
instance uniform float seed = 0.0;
instance uniform float taper = 0.0;       // 1: the tail (y = 0) narrows to nothing (tracers, trails)
instance uniform float shimmer = 0.0;     // scrolling brightness ripple along the beam
uniform float energy = 4.0;
uniform float min_px = 1.6;
uniform sampler2D noise_tex : filter_linear, repeat_enable;

varying float v_len;

void vertex() {
	vec3 a = MODEL_MATRIX[3].xyz;
	vec3 axis = MODEL_MATRIX[1].xyz;
	float len = max(length(axis), 0.0001);
	vec3 dir = axis / len;
	float s = VERTEX.y;
	vec3 p = a + axis * s;
	vec3 to_cam = CAMERA_POSITION_WORLD - p;
	float dist = length(to_cam);
	vec3 side = normalize(cross(dir, to_cam / dist));
	if (jitter > 0.0) {
		vec3 up2 = normalize(cross(dir, side));
		float tick = floor(TIME * 24.0);
		float k = s * len / 7.0;
		float n1 = textureLod(noise_tex, vec2(k * 0.11 + seed, tick * 0.173 + seed * 3.7), 0.0).r - 0.5;
		float n2 = textureLod(noise_tex, vec2(k * 0.11 + seed + 0.37, tick * 0.173 + 0.21), 0.0).g - 0.5;
		float fine = textureLod(noise_tex, vec2(k * 0.6 + seed, tick * 0.31), 0.0).r - 0.5;
		float env = sin(s * 3.14159);
		p += (side * (n1 * 2.6 + fine * 0.8) + up2 * n2 * 2.6) * jitter * env;
	}
	float px = 2.0 * dist / (PROJECTION_MATRIX[1][1] * VIEWPORT_SIZE.y);
	float w = max(width, min_px * px);
	w *= mix(1.0, s, taper);
	p += side * VERTEX.x * w;
	MODELVIEW_MATRIX = VIEW_MATRIX;
	VERTEX = p;
	v_len = len;
}

void fragment() {
	float x = abs(UV.x * 2.0 - 1.0);
	float glow = exp(-x * x * 4.5);
	float c = 1.0 - smoothstep(core * 0.45, core, x);
	float ripple = 1.0;
	if (shimmer > 0.0) {
		ripple = 1.0 + shimmer * (texture(noise_tex, vec2(UV.y * v_len / 18.0 - TIME * 2.5, seed)).r - 0.5) * 2.0;
	}
	float ends = smoothstep(0.0, 0.015, UV.y) * smoothstep(1.0, 0.985, UV.y);
	vec3 col = glow_color.rgb * glow * ripple + core_color.rgb * c * 1.6;
	ALBEDO = col * energy;
	ALPHA = clamp(intensity * ends, 0.0, 1.0);
}
