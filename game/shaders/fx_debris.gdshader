// Debris shards from the EffectsView pool (I87, phase 8 shards): lit, opaque fragments of torn armour, wedges and
// splinters (EffectsView.shard_mesh). The mesh carries every variant; the particle keeps one, picked from its
// random CUSTOM.w, and the others collapse to a point. Facets are bare metal or soot (UV2.y), one end of each
// shard is scorched (UV.x), torn edges catch the light, and the whole piece glows hot for its first moments.
shader_type spatial;
render_mode cull_disabled;

uniform float variants = 6.0;

varying float v_t;
varying vec4 v_col;
varying float v_facet;
varying float v_rand;

void vertex() {
	v_t = clamp(INSTANCE_CUSTOM.x / max(INSTANCE_CUSTOM.y, 0.001), 0.0, 1.0);
	v_col = COLOR;
	v_facet = UV2.y;
	v_rand = INSTANCE_CUSTOM.w;
	float pick = floor(fract(INSTANCE_CUSTOM.w * 7.31 + 0.137) * variants);
	if (abs(UV2.x - pick) > 0.5) {
		VERTEX = vec3(0.0);
	}
	// shrink away at the end instead of popping
	VERTEX *= 1.0 - smoothstep(0.8, 1.0, v_t);
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec3 base = v_col.rgb;
	// facet: bare, scraped metal (lighter, cooler, shinier) or soot-black scorch
	float metal = step(0.55, fract(v_facet + v_rand * 0.37));
	vec3 bare = mix(base * 2.2 + vec3(0.1), vec3(0.58, 0.59, 0.6), 0.5);
	vec3 soot = base * 0.45;
	// one end of the shard scorched, with a ragged edge
	float burn = smoothstep(0.45, 0.85, UV.x + (hash(floor(UV * 9.0) + v_rand) - 0.5) * 0.3);
	if (v_rand > 0.5) burn = 1.0 - burn;
	vec3 col = mix(base * 1.35, bare, metal);
	col = mix(col, soot, burn * 0.55);
	// a scorched heat tint near the burnt end (blued/brown steel)
	col = mix(col, col * vec3(0.95, 0.75, 0.55), burn * (1.0 - burn) * 2.0);
	ALBEDO = col;
	// moderate metallic: the battlefield has no reflection probes, so a full metal reads black
	METALLIC = mix(0.15, 0.5, metal * (1.0 - burn));
	ROUGHNESS = mix(0.92, 0.42, metal * (1.0 - burn));
	SPECULAR = 0.6;
	// hot for the first quarter of the life: glowing at the burnt end first
	float heat = 1.0 - smoothstep(0.0, 0.25, v_t);
	EMISSION = vec3(1.0, 0.45, 0.12) * 3.0 * heat * (0.35 + 0.65 * burn);
}
