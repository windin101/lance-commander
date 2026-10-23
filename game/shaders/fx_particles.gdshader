// Shared particle pool for EffectsView (I87). The GPUParticles3D never emits by itself (emitting = false);
// every particle comes from emit_particle with EMIT_FLAG_CUSTOM: CUSTOM = (age, life, start size, random 0..1).
// One emitter serves every effect on the map and its `amount` is the hard cap. (Emitted particles do not see
// RESTART_CUSTOM in start(), so start() must not filter on it.)
shader_type particles;
render_mode disable_force;

uniform float gravity = 0.0;      // m/s^2 downward; negative rises (buoyant smoke and fire)
uniform float drag = 0.0;         // 1/s
uniform float grow = 0.0;         // size gained over the life, as a multiple of the start size
uniform float grow_power = 0.5;   // <1 grows fast early (puffs), >1 late
uniform float stretch = 0.0;      // streaks: length = speed * stretch (s), never shorter than the width
uniform bool tumble = false;      // debris: spin about a random axis
uniform float spin = 0.0;         // rad/s at random 1.0

void start() {
	CUSTOM.x = 0.0;
}

void process() {
	CUSTOM.x += DELTA;
	if (CUSTOM.x >= CUSTOM.y) {
		ACTIVE = false;
	}
	VELOCITY.y -= gravity * DELTA;
	VELOCITY *= max(0.0, 1.0 - drag * DELTA);
	float t = clamp(CUSTOM.x / max(CUSTOM.y, 0.001), 0.0, 1.0);
	float s = CUSTOM.z * (1.0 + grow * pow(t, grow_power));
	vec3 pos = TRANSFORM[3].xyz;
	if (stretch > 0.0) {
		float sp = length(VELOCITY);
		vec3 dir = sp > 0.01 ? VELOCITY / sp : vec3(0.0, 1.0, 0.0);
		vec3 ref = abs(dir.y) < 0.95 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
		vec3 side = normalize(cross(dir, ref));
		vec3 up = cross(side, dir);
		TRANSFORM[0] = vec4(side * s, 0.0);
		TRANSFORM[1] = vec4(dir * max(s * 2.0, sp * stretch), 0.0);
		TRANSFORM[2] = vec4(up * s, 0.0);
	} else if (tumble) {
		float r = CUSTOM.w;
		vec3 axis = normalize(vec3(sin(r * 91.7), cos(r * 47.3), sin(r * 13.1 + 1.0)));
		float a = (r * 6.2832) + CUSTOM.x * spin * (0.5 + r);
		float c = cos(a);
		float sn = sin(a);
		mat3 rot = mat3(
			vec3(c + axis.x * axis.x * (1.0 - c), axis.y * axis.x * (1.0 - c) + axis.z * sn, axis.z * axis.x * (1.0 - c) - axis.y * sn),
			vec3(axis.x * axis.y * (1.0 - c) - axis.z * sn, c + axis.y * axis.y * (1.0 - c), axis.z * axis.y * (1.0 - c) + axis.x * sn),
			vec3(axis.x * axis.z * (1.0 - c) + axis.y * sn, axis.y * axis.z * (1.0 - c) - axis.x * sn, c + axis.z * axis.z * (1.0 - c)));
		TRANSFORM[0] = vec4(rot[0] * s, 0.0);
		TRANSFORM[1] = vec4(rot[1] * s * 0.6, 0.0);
		TRANSFORM[2] = vec4(rot[2] * s * 0.8, 0.0);
	} else {
		TRANSFORM[0] = vec4(s, 0.0, 0.0, 0.0);
		TRANSFORM[1] = vec4(0.0, s, 0.0, 0.0);
		TRANSFORM[2] = vec4(0.0, 0.0, s, 0.0);
	}
	TRANSFORM[3].xyz = pos;
}
