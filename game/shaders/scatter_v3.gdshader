shader_type spatial;
render_mode specular_disabled;
// Terrain scatter (rocks, pebbles, debris; terrain polish rollout batch 1): the instance colour is the albedo, as the old
// StandardMaterial3D had it, plus the ground's own shadow_fill floor of that colour. On night and airless maps the ground
// is lit almost only by that floor (EMISSION = albedo * shadow_fill in terrain_v3.gdshader), so scatter without one
// rendered pure black beside it.

uniform float fill = 0.05;

void fragment() {
	ALBEDO = COLOR.rgb;
	ROUGHNESS = 0.92;
	EMISSION = COLOR.rgb * fill;
}
