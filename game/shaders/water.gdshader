shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;
// Water: opacity from depth (vertex alpha, from the mission's AlphaShallow/
// Middle/Deep), shallow-to-deep colour, scrolling normals, Fresnel at grazing
// angles, and a gentle swell from the mission's water Frequency/Amplitude.

uniform sampler2D water_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D wave_noise : hint_normal, filter_linear_mipmap, repeat_enable;
uniform vec3 shallow_colour : source_color = vec3(0.28, 0.48, 0.50);
uniform vec3 deep_colour : source_color = vec3(0.06, 0.18, 0.26);
uniform float tiling = 48.0;
uniform float swell_height = 0.35;
uniform float swell_frequency = 0.05;
uniform vec2 flow = vec2(0.012, 0.008);

varying float depth_alpha;

void vertex() {
	depth_alpha = COLOR.a;
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.y += swell_height * sin(wp.x * swell_frequency + TIME * 0.9) * cos(wp.z * swell_frequency * 0.8 + TIME * 0.7) * depth_alpha;
}

void fragment() {
	vec2 uv = UV;
	vec3 n1 = texture(wave_noise, uv * 1.0 + TIME * flow).rgb;
	vec3 n2 = texture(wave_noise, uv * 1.7 - TIME * flow.yx * 1.3).rgb;
	NORMAL_MAP = normalize(mix(n1, n2, 0.5));
	NORMAL_MAP_DEPTH = 0.6;
	vec3 tex = texture(water_tex, uv + TIME * flow * 0.5).rgb;
	float deepness = smoothstep(0.45, 1.0, depth_alpha);
	vec3 colour = mix(shallow_colour, deep_colour, deepness) * (0.75 + 0.5 * tex);
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = colour;
	ROUGHNESS = 0.12;
	METALLIC = 0.0;
	SPECULAR = 0.55;
	ALPHA = clamp(depth_alpha + fresnel * 0.35 * step(0.01, depth_alpha), 0.0, 0.97);
}
