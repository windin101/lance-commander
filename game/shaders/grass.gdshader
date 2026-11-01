shader_type spatial;
render_mode cull_disabled, specular_disabled, depth_draw_opaque;
// Ground cover (terrain polish, 2026-11-01; tools/art/terrain/grass_atlas.py): crossed cards of a blade-clump atlas,
// tinted per instance (COLOR, from the map palette's own ground colours), swaying with a gust that travels across the
// map, lit from above with the card normals bent toward the sky so a clump reads as a soft volume, and a little
// translucency so grass glows when the sun is behind it. Alpha-cut, with the cut raised by mip level so distant
// clumps do not thin out.

uniform sampler2D atlas : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform float wind = 0.5;
uniform float alpha_cut = 0.42;

varying float height_k;
varying float far_k;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float h = clamp(1.0 - UV.y, 0.0, 1.0);   // the cell's v runs top to bottom: 0 at the blade tips
	height_k = h;
	float gust = sin(TIME * 1.3 + dot(origin.xz, vec2(0.11, 0.07))) * 0.6 + sin(TIME * 2.9 + origin.x * 0.31) * 0.25;
	float dist = length(origin - CAMERA_POSITION_WORLD);
	far_k = smoothstep(90.0, 300.0, dist);
	VERTEX.y *= 1.0 - 0.75 * smoothstep(200.0, 320.0, dist);   // clumps sink into the ground toward their range end instead of popping
	VERTEX.x += gust * wind * h * h * 0.22;
	VERTEX.z += cos(TIME * 1.1 + origin.z * 0.09) * wind * h * h * 0.12;
}

void fragment() {
	vec4 t = texture(atlas, UV);
	vec2 px = UV * vec2(textureSize(atlas, 0));
	float lod = max(0.0, log2(max(length(dFdx(px)), length(dFdy(px)))));
	ALPHA = clamp(t.a * (1.0 + lod * 0.45), 0.0, 1.0);
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	vec3 up = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	NORMAL = normalize(mix(NORMAL, up, 0.7));
	vec3 a = t.rgb * COLOR.rgb * (0.7 + 0.3 * height_k);
	ALBEDO = mix(a, COLOR.rgb * 0.26, far_k * 0.6);   // far clumps lose their contrast and fade toward the ground tone
	ROUGHNESS = 1.0;
	BACKLIGHT = ALBEDO * 0.35;
}
