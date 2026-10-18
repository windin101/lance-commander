shader_type spatial;
// Terrain: the mission colour map on flat ground (with the detail texture),
// blending to a triplanar procedural rock on steep slopes so cliff faces are not
// a smear of the top-down colour map. Rock is tinted by the colour map's local
// average, so it follows each map's palette.

uniform sampler2D colour_map : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D detail_map : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D rock_noise : filter_linear_mipmap, repeat_enable;
uniform float detail_tiling = 30.0;
uniform float detail_strength = 0.6;
uniform float rock_scale = 0.14;
uniform float slope_start = 0.32;
uniform float slope_end = 0.62;

varying vec3 world_pos;
varying vec3 world_normal;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

float triplanar(vec3 p, vec3 n) {
	vec3 w = pow(abs(n), vec3(4.0));
	w /= (w.x + w.y + w.z);
	float x = texture(rock_noise, p.zy * rock_scale).r;
	float y = texture(rock_noise, p.xz * rock_scale).r;
	float z = texture(rock_noise, p.xy * rock_scale).r;
	return x * w.x + y * w.y + z * w.z;
}

void fragment() {
	vec3 base = texture(colour_map, UV).rgb;
	vec3 detail = texture(detail_map, UV2).rgb;
	vec3 ground = base * mix(vec3(1.0), detail * 1.6, detail_strength);
	// Facet normal from screen-space derivatives: the smoothed vertex normals average
	// a one-quad cliff with the flat ground around it and never look steep.
	vec3 facet = normalize(cross(dFdy(world_pos), dFdx(world_pos)));
	if (facet.y < 0.0) facet = -facet;
	float slope = 1.0 - clamp(facet.y, 0.0, 1.0);
	float rock_mask = smoothstep(slope_start, slope_end, slope);
	vec3 tint = textureLod(colour_map, UV, 5.0).rgb;
	float n = triplanar(world_pos, facet);
	float n2 = triplanar(world_pos * 3.1, facet);
	float strata = 0.5 + 0.5 * sin(world_pos.y * 0.75 + n * 7.0 + n2 * 3.0);  // irregular rock bands
	vec3 rock = tint * (0.4 + 0.85 * n) * (0.82 + 0.28 * strata) * (0.75 + 0.45 * n2);
	ALBEDO = mix(ground, rock, rock_mask);
	ROUGHNESS = mix(0.95, 0.8, rock_mask);
}
