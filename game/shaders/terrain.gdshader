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
// Ground detail (step 2, tools/art/ground_detail.py): CC0 grain and normals per ground class, classified from
// the colour map's own colour (the map data has no usable terrain types: almost every vertex is "undefined").
// Layers: 0 grass, 1 dirt, 2 rock, 3 sand, 4 snow. The colour stays the colour map's; only grain and relief add.
uniform sampler2DArray detail_l : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray detail_n : filter_linear_mipmap_anisotropic, repeat_enable;
uniform float ground_detail = 0.0;      // grain strength (0 = off)
uniform float ground_relief = 0.0;      // relief shading strength from the detail normals
uniform float detail_fade_near = 150.0;  // metres: full detail inside, fading out to detail_fade_far
uniform float detail_fade_far = 700.0;
uniform int debug_view = 0;  // 1 = grain only, 2 = fade, 3 = class weights
uniform vec3 sun_dir = vec3(0.4, 0.6, -0.5);  // toward the light, world space (mission_view sets it)
const float CLASS_SCALE[5] = {16.0, 20.0, 34.0, 24.0, 28.0};  // metres per tile: grass, dirt, rock, sand, snow

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
	float paved = 0.0;  // cement / overlay cover: no ground grain there
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
			paved = max(paved, w);
		}
		if (cells.r > 0.5) {  // overlay tile (alpha), drawn over everything as the original did
			float c = cells.r - 1.0;
			vec2 org = vec2(mod(c, atlas_cols), floor(c / atlas_cols)) * cell_px + atlas_pad;
			vec4 ov = textureGrad(overlay_atlas, (org + local * atlas_tile) / atlas_px, dl_dx, dl_dy);
			ground = mix(ground, ov.rgb, ov.a);
			paved = max(paved, ov.a);
		}
	}
	vec3 dbg = vec3(-1.0);
	if (ground_detail > 0.0) {
		float dist = length(world_pos - CAMERA_POSITION_WORLD);
		float fade = (1.0 - smoothstep(detail_fade_near, detail_fade_far, dist)) * (1.0 - paved);
		if (fade > 0.001) {
			vec3 lp = textureLod(colour_map, UV, 3.0).rgb;  // about 16 m around: what the ground is, not its speckle
			float mx = max(lp.r, max(lp.g, lp.b));
			float mn = min(lp.r, min(lp.g, lp.b));
			float sat = (mx - mn) / (mx + 1e-4);
			float h = 0.0;
			float dl = mx - mn + 1e-4;
			if (mx == lp.r) h = mod((lp.g - lp.b) / dl, 6.0);
			else if (mx == lp.g) h = (lp.b - lp.r) / dl + 2.0;
			else h = (lp.r - lp.g) / dl + 4.0;
			h *= 60.0;
			float w_snow = smoothstep(0.58, 0.74, mx) * (1.0 - smoothstep(0.10, 0.22, sat));
			float w_grass = smoothstep(0.10, 0.22, sat) * smoothstep(36.0, 50.0, h) * (1.0 - smoothstep(150.0, 175.0, h)) * (1.0 - w_snow);
			float w_sand = smoothstep(0.42, 0.56, mx) * smoothstep(0.14, 0.28, sat) * smoothstep(24.0, 34.0, h) * (1.0 - smoothstep(50.0, 60.0, h));
			float w_rock = max(rock_mask, (1.0 - smoothstep(0.06, 0.14, sat)) * (1.0 - w_snow)) * 0.9;
			float w_dirt = 0.3;
			float ws[5] = {w_grass, w_dirt, w_rock, w_sand, w_snow};
			float tot = w_grass + w_dirt + w_rock + w_sand + w_snow;
			float d = 0.0;
			vec3 nt = vec3(0.0);
			vec2 xz = world_pos.xz;
			vec2 xz2 = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * xz;  // a rotated second octave hides the tiling
			for (int i = 0; i < 5; i++) {
				float w = ws[i] / tot;
				if (w < 0.02) continue;
				float sc = CLASS_SCALE[i];
				float la = texture(detail_l, vec3(xz / sc, float(i))).r;
				float lb = texture(detail_l, vec3(xz2 / (sc * 3.7), float(i))).r;
				d += w * ((mix(la, lb, 0.35) - 0.5) * 2.0);
				vec3 na = texture(detail_n, vec3(xz / sc, float(i))).rgb * 2.0 - 1.0;
				nt += w * na;
			}
			vec3 nw = normalize(vec3(nt.x, max(nt.z, 0.2), -nt.y));
			float relief = (dot(nw, sun_dir) - sun_dir.y) / max(sun_dir.y, 0.3);
			if (debug_view == 1) dbg = vec3(0.5 + d * 0.5);
			if (debug_view == 2) dbg = vec3(fade);
			if (debug_view == 4) dbg = textureLod(detail_l, vec3(world_pos.xz / 3.0, 0.0), 0.0).rgb;
			if (debug_view == 5) dbg = vec3(fract(world_pos.xz / 3.0), 0.0);
			if (debug_view == 3) dbg = vec3(w_grass, w_rock, w_snow + w_sand * 0.5) / tot;
			ground *= (1.0 + fade * ground_detail * d) * (1.0 + fade * ground_relief * clamp(relief, -0.6, 0.6));
		}
	}
	ALBEDO = ground * mix(1.0, grain, rock_mask * rock_grain);
	if (dbg.x >= 0.0) ALBEDO = dbg;
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
