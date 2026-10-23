shader_type spatial;
// v2 building surfaces (HD rework, 2026-10-23; tools/art/hd_v2_building.py): a tiling PBR set per surface type on
// UV (metres / 2), an ambient-occlusion bake on UV2, weathering from the shared grunge, the mission's dust and snow
// (MechPaint.env_*). Glass is a dark, glossy pane with a faint warm glow from inside.
render_mode depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;  // RGB + roughness in A
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D ao_tex : hint_default_white, filter_linear_mipmap;
uniform sampler2D grunge_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 tint : source_color = vec3(1.0);
uniform float metallic = 0.0;
uniform float is_glass = 0.0;
uniform float normal_depth = 1.0;
uniform float dust : hint_range(0.0, 1.0) = 0.25;
uniform float snow : hint_range(0.0, 1.0) = 0.0;
uniform vec3 dust_colour : source_color = vec3(0.56, 0.5, 0.4);
uniform float scorch : hint_range(0.0, 1.0) = 0.0;

varying vec3 world_n;
varying float rel_h;

void vertex() {
	world_n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	rel_h = VERTEX.y;
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	float ao = texture(ao_tex, UV2).r;
	vec4 g = texture(grunge_tex, UV * 0.37);
	vec3 col = a.rgb * tint * (0.9 + 0.2 * g.g);
	float rough = a.a;
	// runs of grime below ledges, more low down
	float low = 1.0 - smoothstep(0.0, 2.5, rel_h);
	float grime = clamp((1.0 - ao) * 0.8 + low * 0.35 * g.r + smoothstep(0.55, 0.8, g.a) * 0.3, 0.0, 0.85);
	col = mix(col, col * vec3(0.4, 0.36, 0.3), grime);
	float up = clamp(world_n.y, 0.0, 1.0);
	float dm = clamp(dust * (smoothstep(0.3, 0.9, up) * 0.7 + low * 0.8 + (1.0 - ao) * 0.4) * (0.6 + 0.8 * g.g), 0.0, 1.0);
	col = mix(col, dust_colour * (0.85 + 0.3 * g.b), dm * 0.8);
	float sm = clamp(snow * smoothstep(0.4, 0.8, up + (g.g - 0.5) * 0.3) * 1.6, 0.0, 1.0);
	col = mix(col, vec3(0.88, 0.9, 0.93), sm);
	col = mix(col, vec3(0.05, 0.045, 0.04), scorch * 0.85);
	if (is_glass > 0.5) {
		ALBEDO = vec3(0.03, 0.04, 0.05);
		METALLIC = 0.0;
		ROUGHNESS = 0.08 + 0.2 * g.b;
		SPECULAR = 0.7;
		EMISSION = vec3(0.9, 0.6, 0.3) * 0.05 * (0.6 + 0.4 * g.r);
	} else {
		ALBEDO = col;
		METALLIC = metallic * (1.0 - dm);
		ROUGHNESS = clamp(mix(rough + dm * 0.3, 0.7, sm), 0.05, 1.0);
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		NORMAL_MAP_DEPTH = normal_depth;
	}
	AO = ao;
	AO_LIGHT_AFFECT = 0.6;
}
