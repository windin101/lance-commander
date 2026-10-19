shader_type spatial;
render_mode cull_disabled, specular_disabled, depth_draw_opaque;
// HD tree foliage (tools/art/trees.py): leaf-cluster cards cut out with alpha, tinted per tree (COLOR, from the
// original's leaf colour), with normals pointing out of the crown so the crown lights as a volume. Back faces
// keep the same normal (no flip), as a crown has no "back". Wind: a slow sway growing with height, phased by
// the tree's world position so a forest does not move in step. Alpha is raised with distance so mipmapped
// foliage does not thin out.

uniform sampler2D leaf_atlas : source_color, filter_linear_mipmap_anisotropic;
uniform float wind_strength = 0.18;
uniform float alpha_cut = 0.45;

varying vec3 crown_normal;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float phase = dot(origin.xz, vec2(0.037, 0.053));
	float h = max(VERTEX.y, 0.0);
	float sway = sin(TIME * 0.9 + phase) * 0.6 + sin(TIME * 2.3 + phase * 1.7) * 0.25;
	VERTEX.x += sway * wind_strength * h * 0.08;
	VERTEX.z += cos(TIME * 0.7 + phase) * wind_strength * h * 0.04;
	crown_normal = (MODELVIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
}

void fragment() {
	vec4 t = texture(leaf_atlas, UV);
	vec2 px = UV * vec2(textureSize(leaf_atlas, 0));
	float lod = max(0.0, log2(max(length(dFdx(px)), length(dFdy(px)))));
	ALBEDO = t.rgb * COLOR.rgb;
	ALPHA = clamp(t.a * (1.0 + lod * 0.35), 0.0, 1.0);
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	NORMAL = normalize(crown_normal);
	ROUGHNESS = 1.0;
	BACKLIGHT = vec3(0.25) * COLOR.rgb;
}
