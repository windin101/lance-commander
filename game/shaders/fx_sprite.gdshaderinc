// Draw pass for the EffectsView particle pools (see fx_particles.gdshader for CUSTOM).
uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D ramp : source_color, filter_linear, repeat_disable;  // fire: intensity -> colour
uniform int cells = 1;            // sheet cells per side; each particle keeps one random cell
uniform bool streak = false;      // align to the particle's Y axis (its velocity), head at the top
uniform bool use_ramp = false;
uniform float energy = 1.0;
uniform float fade_in = 0.05;
uniform float fade_out = 0.4;     // fraction of the life at which the fade out begins
uniform float spin = 0.0;
uniform float cool = 0.0;         // fire: intensity lost over the life (white-hot -> red -> smoke)
uniform float soft = 0.0;         // depth fade distance in metres (0 = off)
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;

varying float v_t;
varying vec4 v_col;
varying vec2 v_uv;

void vertex() {
	float life = max(INSTANCE_CUSTOM.y, 0.001);
	v_t = clamp(INSTANCE_CUSTOM.x / life, 0.0, 1.0);
	v_col = COLOR;
	float r = INSTANCE_CUSTOM.w;
	int cell = int(floor(r * 997.0)) % (cells * cells);
	v_uv = (UV + vec2(float(cell % cells), float(cell / cells))) / float(cells);
	vec3 origin = MODEL_MATRIX[3].xyz;
	if (streak) {
		vec3 axis = MODEL_MATRIX[1].xyz;
		float w = length(MODEL_MATRIX[0].xyz);
		vec3 to_cam = normalize(CAMERA_POSITION_WORLD - origin);
		vec3 dir = normalize(axis);
		vec3 side = normalize(cross(dir, to_cam)) * w;
		vec3 world = origin + axis * (VERTEX.y - 0.5) + side * VERTEX.x * 2.0;
		MODELVIEW_MATRIX = VIEW_MATRIX;
		VERTEX = world;
		NORMAL = to_cam;
	} else {
		float s = length(MODEL_MATRIX[0].xyz);
		float a = r * 6.2832 + INSTANCE_CUSTOM.x * spin * (r - 0.5) * 2.0;
		vec2 v = mat2(vec2(cos(a), sin(a)), vec2(-sin(a), cos(a))) * VERTEX.xy * s;
		vec3 world = origin + INV_VIEW_MATRIX[0].xyz * v.x + INV_VIEW_MATRIX[1].xyz * v.y;
		MODELVIEW_MATRIX = VIEW_MATRIX;
		VERTEX = world;
		NORMAL = INV_VIEW_MATRIX[2].xyz;
	}
	MODELVIEW_NORMAL_MATRIX = mat3(VIEW_MATRIX);
}

float fx_alpha(vec2 screen_uv, vec3 vertex, mat4 inv_proj) {
	float a = smoothstep(0.0, max(fade_in, 0.0001), v_t) * (1.0 - smoothstep(fade_out, 1.0, v_t));
	if (soft > 0.0) {
		float depth = textureLod(depth_tex, screen_uv, 0.0).r;
		vec4 ndc = vec4(screen_uv * 2.0 - 1.0, depth, 1.0);
		vec4 view = inv_proj * ndc;
		float scene_z = -view.z / view.w;
		a *= clamp((scene_z + vertex.z) / soft, 0.0, 1.0);
	}
	return a;
}
