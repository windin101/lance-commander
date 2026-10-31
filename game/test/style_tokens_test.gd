extends GdUnitTestSuite
## The style guide's tokens (docs/art/STYLE-GUIDE.md 2.1, 3, 4) in res://data/theme/style_tokens.json, the
## constants that mirror them, the Theme built from them, and the 2.3 role schemes.


func test_every_palette_token_is_in_the_json_with_the_guides_hex() -> void:
	var want := {"ink-900": "#070A0D", "ink-800": "#0C1117", "ink-700": "#121A22", "ink-600": "#1B2630",
		"steel-500": "#3A4854", "steel-300": "#7F909C", "steel-100": "#D5DEE3", "white": "#F2F6F8",
		"amber-500": "#F2A21F", "amber-300": "#FFC85A", "amber-700": "#8C5A0C", "cyan-400": "#3FC6E0",
		"ok": "#4FD38A", "warn": "#F2B54A", "heat": "#FF7A2F", "crit": "#FF5A4E", "friend": "#5CA0FF", "neutral": "#C9CED2"}
	for k in want:
		assert_str(String(StyleTokens.data()["colour"][k])).is_equal(want[k])
	assert_float(StyleTokens.color("cyan-glow").a).is_equal_approx(0.4, 0.002)


func test_ui_style_constants_mirror_the_tokens() -> void:
	var pairs := {"ink-900": UiStyle.INK_900, "ink-800": UiStyle.INK_800, "ink-700": UiStyle.INK_700,
		"ink-600": UiStyle.INK_600, "steel-500": UiStyle.STEEL_500, "steel-300": UiStyle.STEEL_300,
		"steel-100": UiStyle.STEEL_100, "white": UiStyle.WHITE, "amber-500": UiStyle.AMBER_500,
		"amber-300": UiStyle.AMBER_300, "amber-700": UiStyle.AMBER_700, "cyan-400": UiStyle.CYAN_400,
		"ok": UiStyle.STATE_OK, "warn": UiStyle.WARN, "heat": UiStyle.HEAT, "crit": UiStyle.CRIT,
		"friend": UiStyle.FRIEND, "neutral": UiStyle.NEUTRAL}
	for k in pairs:
		assert_str((pairs[k] as Color).to_html(false)).is_equal(StyleTokens.color(k).to_html(false))
	# the HUD constants the guide keeps (19.2) are the same tokens
	assert_str(UiStyle.HUD_EDGE.to_html(false)).is_equal(UiStyle.CYAN_400.to_html(false))
	assert_str(UiStyle.HUD_CRIT.to_html(false)).is_equal(UiStyle.CRIT.to_html(false))


func test_green_accent_is_gone_and_amber_leads() -> void:
	# 19.1: menus and debrief move to amber; green is only `ok`
	assert_str(UiStyle.ACCENT.to_html(false)).is_equal("f2a21f")
	for f in ["res://scripts/ui/ui_style.gd", "res://scripts/ui/debrief.gd", "res://scripts/ui/main_menu.gd",
			"res://scripts/ui/style_tokens.gd"]:
		var src := FileAccess.get_file_as_string(f).to_lower()
		assert_bool(src.contains("73ff8c") or src.contains("0.45, 1.0, 0.55")).is_false()


func test_type_and_geometry_tokens() -> void:
	assert_int(StyleTokens.size("title")).is_equal(40)
	assert_int(StyleTokens.size("label")).is_equal(13)
	assert_int(StyleTokens.size("banner")).is_equal(56)
	assert_float(StyleTokens.geo("chamfer_panel")).is_equal(10.0)
	assert_float(StyleTokens.geo("corner_radius")).is_equal(0.0)
	assert_float(StyleTokens.motion_s("slow")).is_equal_approx(0.18, 0.0001)
	for role in ["display", "body", "label", "numeric"]:
		assert_object(StyleTokens.font(role, 16)).is_not_null()
		assert_bool(StyleTokens.font(role) == ThemeDB.fallback_font).is_false()  # the bundled OFL file loaded


func test_theme_uses_chamfered_frames_and_amber_buttons() -> void:
	var t := StyleTokens.theme()
	var b := t.get_stylebox("normal", "Button")
	assert_bool(b is StyleTokens.ChamferBox).is_true()
	assert_float((b as StyleTokens.ChamferBox).cut).is_equal(6.0)
	assert_str((b as StyleTokens.ChamferBox).edge.to_html(false)).is_equal("f2a21f")
	assert_bool(t.get_stylebox("panel", "PanelContainer") is StyleTokens.ChamferBox).is_true()
	assert_str(t.get_type_variation_base("SecondaryButton")).is_equal("Button")
	assert_str(t.get_type_variation_base("TitleLabel")).is_equal("Label")
	assert_bool(UiStyle.theme() == t).is_true()


func test_chamfer_outline_cuts_all_four_corners() -> void:
	var o := StyleTokens.ChamferBox.outline(Rect2(0, 0, 100, 50), 10)
	assert_int(o.size()).is_equal(8)
	assert_bool(o.has(Vector2(0, 0))).is_false()


func test_main_menu_builds() -> void:
	var m: Control = load("res://scenes/main_menu.tscn").instantiate()
	add_child(m)
	await get_tree().process_frame
	for id in ["new", "continue", "skirmish", "options", "exit"]:
		assert_bool(m.buttons.has(id)).is_true()
	assert_bool((m.buttons["skirmish"] as Button).disabled).is_true()
	m.queue_free()


func test_faction_schemes_are_the_guides_roles() -> void:
	var want := {"player_default": ["#4a5560", "#f2a21f", "#d5dee3"], "opfor": ["#5a2a26", "#2a2a2c", "#b8b2a6"],
		"davion": ["#b0262b", "#e8c14a", "#1a1a1a"], "steiner": ["#2c4f9e", "#d8dce0", "#e8c14a"],
		"realm_crimson_black": ["#7a1d24", "#1e1e22", "#c9a646"], "liao": ["#2f6b4f", "#c9a646", "#1e1e22"],
		"realm_purple": ["#6e3a8a", "#d8dce0", "#c9a646"], "clans": ["#3e4a44", "#b7792b", "#0e0e10"],
		"civilian": ["#c9a230", "#5b6770", "#1e1e22"]}
	for k in want:
		var s := PaintScheme.named(k)
		assert_array([s["base"], s["hl1"], s["hl2"]]).is_equal(want[k])
	# 2.3 licence rule: the UI labels schemes by role, never by house name
	for k in PaintScheme.data()["schemes"]:
		var label := String(PaintScheme.data()["schemes"][k].get("display_name", "")).to_lower()
		for house in ["davion", "steiner", "liao", "kurita", "marik", "lyran", "capellan", "draconis", "federated"]:
			assert_bool(label.contains(house)).is_false()


func test_v3_shader_takes_the_scheme_colours() -> void:
	# ArtV3.paint_colour keeps paint inside the PBR range: amber's value 0.95 is held at 0.88, hue kept
	var amber := Color("#f2a21f")
	var c := ArtV3.paint_colour(amber).linear_to_srgb()
	assert_float(c.h).is_equal_approx(amber.h, 0.01)
	assert_float(c.v).is_equal_approx(0.88, 0.01)
	var blue := Color("#2c4f9e")  # inside the range: unchanged
	assert_str(ArtV3.paint_colour(blue).linear_to_srgb().to_html(false)).is_equal(blue.to_html(false))


func test_reduce_motion_is_saved() -> void:
	var keep := StyleTokens.settings_path
	StyleTokens.settings_path = "user://test_style_settings.cfg"
	StyleTokens.set_reduce_motion(true)
	StyleTokens._reduce = -1  # force a re-read from the file
	assert_bool(StyleTokens.reduce_motion()).is_true()
	StyleTokens.set_reduce_motion(false)
	StyleTokens._reduce = -1
	assert_bool(StyleTokens.reduce_motion()).is_false()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(StyleTokens.settings_path))
	StyleTokens.settings_path = keep
	StyleTokens._reduce = -1


func test_bay_kit_layers() -> void:
	# the amber layer (briefing, bay, lab, pause) vs the cyan HUD
	var hud := BayKit.new(11.4)
	assert_str(hud.accent.to_html(false)).is_equal(UiStyle.CYAN_400.to_html(false))
	assert_bool(hud.frame() is UiStyle.HudFrame).is_true()
	var menu := BayKit.new(11.4)
	menu.set_amber()
	assert_str(menu.accent.to_html(false)).is_equal(UiStyle.AMBER_500.to_html(false))
	assert_bool(menu.frame() is StyleTokens.ChamferBox).is_true()
	var b := menu.primary(Button.new())
	assert_str((b.get_theme_stylebox("normal") as StyleTokens.ChamferBox).edge.to_html(false)).is_equal("f2a21f")
	b.free()
	# 6: HUD frame line-work at 80 %, panels ink-700 at 80 %
	assert_float(UiStyle.HudFrame.new().edge.a).is_equal_approx(0.8, 0.001)
	assert_str(UiStyle.HUD_PANEL.to_html(false)).is_equal(UiStyle.INK_700.to_html(false))


func test_bay_stage_is_the_hangar_and_reviews_stay_neutral() -> void:
	# guide 5.5: the bay and lab stage is lit as a hangar (cold overhead key, amber work-lights, haze);
	# a Studio built directly (art_gallery, vehicle_gallery, Thumbs) keeps the neutral review lighting
	var vp := SubViewport.new()
	add_child(vp)
	var neutral := MechStage.Studio.new(vp)
	assert_str(neutral.look).is_equal("neutral")
	assert_int(neutral.work_lights.size()).is_equal(0)
	assert_bool(neutral.env.fog_enabled).is_false()
	var lights := vp.find_children("*", "DirectionalLight3D", true, false)
	assert_bool(lights.any(func(l): return (l as DirectionalLight3D).light_color.is_equal_approx(UiStyle.CYAN_400))).is_true()
	vp.queue_free()
	var vp2 := SubViewport.new()
	add_child(vp2)
	var hangar := MechStage.Studio.new(vp2, "hangar")
	assert_int(hangar.work_lights.size()).is_equal(2)
	assert_bool(hangar.env.fog_enabled).is_true()
	assert_bool(vp2.find_children("*", "DirectionalLight3D", true, false).any(
		func(l): return (l as DirectionalLight3D).light_color.is_equal_approx(UiStyle.CYAN_400))).is_false()
	assert_float(hangar.work_lights[0].light_color.r).is_greater(hangar.work_lights[0].light_color.b)  # amber
	vp2.queue_free()
	var stage := MechStage.new()
	assert_str(stage.studio.look).is_equal("hangar")
	stage.free()


func test_pause_menu_lists_the_objectives() -> void:
	# 5.12: RESUME, OBJECTIVES, OPTIONS (inline), ABORT MISSION
	var view: Node3D = auto_free(load("res://scenes/mission_view.tscn").instantiate())
	view.play_intro = false
	add_child(view)
	await get_tree().process_frame
	var pm: PauseMenu = view.pause_menu
	pm.open_pause()
	var labels := pm.buttons.get_children().map(func(b): return (b as Button).text)
	assert_array(labels).contains(["RESUME", "OBJECTIVES", "ABORT MISSION"])
	assert_bool(pm.motion_button != null).is_true()
	pm._toggle_objectives()
	assert_object(pm._objectives).is_not_null()
	var n: int = view.sm.objectives.visible_objectives().size()
	assert_int(pm._objectives.get_child_count()).is_equal(2 + maxi(1, n))  # heading, rule, one row each
	pm.close()
	assert_object(pm._objectives).is_null()
	assert_bool(get_tree().paused).is_false()
