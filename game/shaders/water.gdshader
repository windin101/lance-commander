shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;
// Water (2026-10-20, closer to the original's quad.cpp:1974-2156): the mission's water texture is the
// colour, tiled WaterTextureTilingFactor times with a slow circular drift; over it the mission's 16-frame
// sparkle layer (<mission>.water0000..0015, white with alpha) ping-pongs at 8 fps, tiled
// WaterDetailTilingFactor times and scrolling. Opacity per vertex from the mission's AlphaShallow/Middle/
// Deep (COLOR.a). Scrolling normals, Fresnel and a gentle swell are the remake's additions.

uniform sampler2D water_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D detail_atlas : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D wave_noise : hint_normal, filter_linear_mipmap, repeat_enable;
uniform float tiling = 48.0;
uniform float detail_tiling = 45.0;
uniform float detail_strength = 0.0;
uniform float swell_height = 0.35;
uniform float swell_frequency = 0.05;
uniform vec2 flow = vec2(0.012, 0.008);

varying float depth_alpha;

void vertex() {
	depth_alpha = COLOR.a;
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.y += swell_height * sin(wp.x * swell_frequency + TIME * 0.9) * cos(wp.z * swell_frequency * 0.8 + TIME * 0.7) * depth_alpha;
}

vec4 sparkle(vec2 uv) {
	float f = mod(floor(TIME * 8.0), 30.0);
	float frame = f < 16.0 ? f : 30.0 - f;  // ping-pong 0..15..1
	vec2 cell = vec2(mod(frame, 4.0), floor(frame / 4.0));
	return texture(detail_atlas, (fract(uv) + cell) / 4.0);
}

void fragment() {
	vec2 drift = 0.02 * vec2(cos(TIME * 0.25), sin(TIME * 0.25));
	vec2 uv = UV * tiling + drift;
	vec3 n1 = texture(wave_noise, UV * tiling * 0.25 + TIME * flow).rgb;
	vec3 n2 = texture(wave_noise, UV * tiling * 0.42 - TIME * flow.yx * 1.3).rgb;
	NORMAL_MAP = normalize(mix(n1, n2, 0.5));
	NORMAL_MAP_DEPTH = 0.5;
	vec3 colour = texture(water_tex, uv).rgb;
	float deepness = smoothstep(0.55, 1.0, depth_alpha);
	colour *= mix(vec3(1.45, 1.55, 1.45), vec3(0.85), deepness);  // shallows lighter and greener, so the bed reads
	vec4 sp = sparkle(UV * detail_tiling + TIME * vec2(0.01, 0.006));
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = colour;
	EMISSION = vec3(sp.a * detail_strength * 0.9);
	ROUGHNESS = 0.12;
	METALLIC = 0.0;
	SPECULAR = 0.5;
	ALPHA = clamp(depth_alpha + fresnel * 0.3 * step(0.01, depth_alpha), 0.0, 0.97);
}
