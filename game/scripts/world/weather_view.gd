class_name WeatherView
extends Node3D
## Rain and lightning from the mission FIT's [Weather] block (only mc2_10 rains: 500 drops, rain level 3,
## lightning chance 0.04; mc2_19 has lightning without rain). The original (Code/weather.cpp) drew rain drops
## around the camera, dimmed the lit terrain by the rain level and flashed the scene with lightning
## (quad.cpp:813-823). Here: a GPU particle box of streaks that follows the camera's focus, a dimmer sun and
## ambient while it rains, and short double flashes of the sun and ambient at the mission's chance per second.

var camera: RtsCamera
var sun: DirectionalLight3D
var env: Environment
var lightning_chance := 0.0  # per second
var _rain: GPUParticles3D
var _sun_energy := 1.0
var _ambient_energy := 1.0
var _flash := 0.0
var _flash_steps: Array[float] = []
var _rng := RandomNumberGenerator.new()


func setup(weather: Dictionary, cam: RtsCamera, sun_light: DirectionalLight3D, environment: Environment) -> void:
	camera = cam
	sun = sun_light
	env = environment
	_rng.seed = 2026
	var drops := int(weather.get("MaxRainDrops", 0))
	var level := float(weather.get("StartingRainLevel", 0.0))
	lightning_chance = float(weather.get("BaseLighteningChance", 0.0))
	if drops > 0 and level > 0.0:
		var dim := clampf(1.0 - 0.08 * level, 0.6, 1.0)  # rainLightLevel: heavier rain, darker world
		sun.light_energy *= dim
		env.ambient_light_energy *= dim
		_rain = _make_rain(drops)
		add_child(_rain)
	_sun_energy = sun.light_energy
	_ambient_energy = env.ambient_light_energy


func _make_rain(drops: int) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Rain"
	p.amount = clampi(drops * 8, 500, 6000)
	p.lifetime = 1.2
	p.preprocess = 1.2
	p.visibility_aabb = AABB(Vector3(-200, -120, -200), Vector3(400, 240, 400))
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = Vector3(90, 2, 90)
	m.direction = Vector3(0.12, -1, 0.05)
	m.spread = 2.0
	m.initial_velocity_min = 55.0
	m.initial_velocity_max = 70.0
	m.gravity = Vector3(0, -20, 0)
	p.process_material = m
	var streak := QuadMesh.new()
	streak.size = Vector2(0.18, 3.5)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = Color(0.78, 0.82, 0.9, 0.3)
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	streak.material = mat
	p.draw_pass_1 = streak
	return p


func _process(delta: float) -> void:
	if _rain and camera:
		# halfway between the lens and the focus, so drops pass close to the camera at any zoom
		var mid := camera.global_position.lerp(camera.focus, 0.45)
		_rain.global_position = mid + Vector3(0, 45.0, 0)
	if lightning_chance > 0.0 and _flash_steps.is_empty() and _rng.randf() < lightning_chance * delta:
		_flash_steps = [0.06, 0.08, 0.05, 0.18]  # on, off, on, fade: a double strike
		_flash = 0.0
	if not _flash_steps.is_empty():
		_flash += delta
		var lit := (_flash_steps.size() % 2) == 0
		var k := 1.0 if lit else 0.0
		if _flash_steps.size() == 1:
			k = 1.0 - clampf(_flash / _flash_steps[0], 0.0, 1.0)
		sun.light_energy = _sun_energy * (1.0 + 2.5 * k)
		env.ambient_light_energy = _ambient_energy * (1.0 + 1.5 * k)
		if _flash >= _flash_steps[0]:
			_flash = 0.0
			_flash_steps.pop_front()
			if _flash_steps.is_empty():
				sun.light_energy = _sun_energy
				env.ambient_light_energy = _ambient_energy
