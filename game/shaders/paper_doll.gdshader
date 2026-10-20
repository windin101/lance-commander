shader_type canvas_item;
// Paper doll from an index mask (assets/ui/dolls/<unit>_doll.png, R = location index, 255 empty):
// each location filled in its colour at fill_alpha, with full-alpha borders where the index changes
// (between locations and at the silhouette). colors[i].a scales a location (0 hides it). One shader
// for the systems monitor and the lance cards (MissionHud).

uniform vec4 colors[8];
uniform int count = 8;
uniform float fill_alpha = 0.35;
uniform float edge_px = 1.0;

// a macro, not a function: TEXTURE can't be passed to functions on every renderer
#define index_at(uv) int(round(texture(TEXTURE, uv).r * 255.0))

void fragment() {
	int i = index_at(UV);
	vec2 d = fwidth(UV) * edge_px;
	int l = index_at(UV - vec2(d.x, 0.0));
	int r = index_at(UV + vec2(d.x, 0.0));
	int t = index_at(UV - vec2(0.0, d.y));
	int b = index_at(UV + vec2(0.0, d.y));
	if (i >= count) {
		// outside: draw the silhouette edge of the neighbour, half a stroke outward
		int n = l < count ? l : (r < count ? r : (t < count ? t : b));
		if (n < count) {
			COLOR = vec4(colors[n].rgb, colors[n].a);
		} else {
			COLOR = vec4(0.0);
		}
	} else {
		vec4 c = colors[i];
		bool edge = l != i || r != i || t != i || b != i;
		COLOR = vec4(c.rgb, edge ? c.a : c.a * fill_alpha);
	}
}
