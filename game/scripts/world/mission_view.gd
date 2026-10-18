extends Node3D
## Loads a mission's terrain and shows it with the mission's own lighting
## (the [Cameras] block of the mission FIT). Phase 3 test bed.

@export var mission := "mc2_01"
@export var show_debug_path := true

var map: SimMap
var camera: RtsCamera


func _ready() -> void:
	map = SimMap.load_mission(mission)
	map.forest_cost = float(GameData.gamesys["General"].get("ForestMoveCost", 50))
	var mission_fit: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/missions/%s.json" % mission))
	var cam_block: Dictionary = mission_fit.get("Cameras", {})

	var terrain := TerrainView.new()
	terrain.name = "Terrain"
	add_child(terrain)
	terrain.build(map, "res://assets/maps/%s" % mission)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = _rgb(cam_block, "Light", Color(1, 1, 0.88))
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 1500.0
	var pitch := float(cam_block.get("LightDirPitch", 50.0))
	var yaw := float(cam_block.get("LightDirYaw", 11.0))
	sun.rotation_degrees = Vector3(-pitch, -yaw, 0)
	add_child(sun)

	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = _rgb(cam_block, "Ambient", Color(0.28, 0.28, 0.31))
	env.ambient_light_energy = 1.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ssao_enabled = true
	env.glow_enabled = true
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)

	camera = RtsCamera.new()
	camera.name = "Camera"
	camera.far = 6000.0
	camera.bounds_half = map.half_m
	camera.height_at = map.height_at
	camera.yaw_deg = float(cam_block.get("StartRotation", 0.0))
	var start := Vector2(float(cam_block.get("PositionX", 0.0)), float(cam_block.get("PositionY", 0.0))) * map.meters_per_wu
	camera.focus = Vector3(start.x, 0, -start.y)
	add_child(camera)
	camera.make_current()

	if show_debug_path:
		_draw_debug_path()


func _rgb(block: Dictionary, prefix: String, fallback: Color) -> Color:
	if not block.has(prefix + "Red"):
		return fallback
	return Color8(int(block[prefix + "Red"]), int(block[prefix + "Green"]), int(block[prefix + "Blue"]))


## Path between the two most distant walkable points on a diagonal, drawn as a line.
func _draw_debug_path() -> void:
	var a := map.nearest_walkable(Vector2(-map.half_m * 0.5, map.half_m * 0.3))
	var b := map.nearest_walkable(Vector2(map.half_m * 0.45, -map.half_m * 0.35))
	var path := map.find_path(a, b)
	if path.size() < 2:
		push_warning("debug path: no route found")
		return
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_LINE_STRIP)
	for p in path:
		st.add_vertex(TerrainView.to_3d(p, map.height_at(p) + 2.0))
	var line := MeshInstance3D.new()
	line.name = "DebugPath"
	line.mesh = st.commit()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(1.0, 0.2, 0.1)
	mat.no_depth_test = true
	line.material_override = mat
	add_child(line)
