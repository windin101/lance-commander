shader_type spatial;
render_mode ambient_light_disabled, specular_disabled;
// Terrain, drawn the way MechCommander 2 drew it (2026-10-20, docs/terrain-rendering.md):
// the mission colour map ("burn-in") already carries the sun's shading and cast shadows, painted by the
// editor (terrtxm2.cpp burnInShadows), and the original drew it UNLIT (quad.cpp:1439-1441). So the ground
// shows the colour map as painted: no ambient, no N.L. The sun only adds the dynamic shadows of mechs,
// vehicles, buildings and trees (the ground itself casts none: its hills are already shaded in the map),
// darkened to `shadow_floor`. Other lights (explosions, flashes) add on top, lit by N.L as the original's
// point lights were.
// Detail: the original alpha-blends the detail texture over the colour map with the texture's own alpha
// (gos_Alpha_AlphaInvAlpha, a dark grey at about 10-20 %), tiled DetailTextureTilingFactor times.
// Steep slopes keep the painted colour map and gain a light triplanar rock grain, so cliffs read as rock
// up close without overwriting the artists' painted rock bands.

uniform sampler2D colour_map : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D detail_map : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_noise : filter_linear_mipmap, repeat_enable;
uniform float detail_strength = 1.0;   // 1 = the original blend
uniform float rock_scale = 0.14;
uniform float rock_grain = 0.35;       // how much the rock grain modulates steep slopes (0 = none)
uniform float slope_start = 0.32;
uniform float slope_end = 0.62;
uniform vec3 shadow_floor = vec3(0.62, 0.63, 0.68);  // lit fraction inside a dynamic shadow (per mission)
// Road/runway/bridge overlay tiles and cement pads (terrain_view.gd _overlay_layer)
uniform sampler2D overlay_atlas : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D overlay_index : filter_nearest;
uniform sampler2D cement_weight : filter_linear;
uniform float atlas_cols = 22.0;
uniform float atlas_tile = 64.0;
uniform float atlas_pad = 2.0;
uniform float vertices_per_side = 0.0;  // 0 = no overlay layer

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
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
	vec4 detail = texture(detail_map, UV2);
	vec3 ground = mix(base, detail.rgb, detail.a * detail_strength);
	vec3 facet = normalize(cross(dFdy(world_pos), dFdx(world_pos)));
	if (facet.y < 0.0) facet = -facet;
	float slope = 1.0 - clamp(facet.y, 0.0, 1.0);
	float rock_mask = smoothstep(slope_start, slope_end, slope);
	float n = triplanar(world_pos, facet);
	float n2 = triplanar(world_pos * 3.1, facet);
	float grain = (0.55 + 0.9 * n) * (0.8 + 0.4 * n2);
	if (vertices_per_side > 0.0) {
		vec2 qf = UV * vertices_per_side;
		ivec2 q = clamp(ivec2(floor(qf)), ivec2(0), ivec2(int(vertices_per_side) - 1));
		vec2 local = fract(qf);
		vec2 cells = texelFetch(overlay_index, q, 0).rg;
		float cell_px = atlas_tile + 2.0 * atlas_pad;
		vec2 atlas_px = vec2(atlas_cols * cell_px);
		vec2 dl_dx = dFdx(qf) * atlas_tile / atlas_px;
		vec2 dl_dy = dFdy(qf) * atlas_tile / atlas_px;
		if (cells.g > 0.5) {  // cement: the tile across the quad, faded in from the cement vertices
			float c = cells.g - 1.0;
			vec2 org = vec2(mod(c, atlas_cols), floor(c / atlas_cols)) * cell_px + atlas_pad;
			vec3 cem = textureGrad(overlay_atlas, (org + local * atlas_tile) / atlas_px, dl_dx, dl_dy).rgb;
			float w = smoothstep(0.3, 0.9, texture(cement_weight, (qf + 0.5) / vertices_per_side).r);
			ground = mix(ground, cem, w);
		}
		if (cells.r > 0.5) {  // overlay tile (alpha), drawn over everything as the original did
			float c = cells.r - 1.0;
			vec2 org = vec2(mod(c, atlas_cols), floor(c / atlas_cols)) * cell_px + atlas_pad;
			vec4 ov = textureGrad(overlay_atlas, (org + local * atlas_tile) / atlas_px, dl_dx, dl_dy);
			ground = mix(ground, ov.rgb, ov.a);
		}
	}
	ALBEDO = ground * mix(1.0, grain, rock_mask * rock_grain);
	ROUGHNESS = 0.95;
}

void light() {
	if (LIGHT_IS_DIRECTIONAL) {
		// the sun: the colour map as painted, darkened only where something casts a shadow on it
		DIFFUSE_LIGHT += mix(shadow_floor, vec3(1.0), ATTENUATION);
	} else {
		DIFFUSE_LIGHT += LIGHT_COLOR * ATTENUATION * max(dot(NORMAL, LIGHT), 0.0) / PI;
	}
}
