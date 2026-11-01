extends Control
## Dev: the comms window as the HUD draws it, four times (a clean pilot, the same pilot wounded and
## dead (memorial portrait), the tac officer's voice-over), for the portrait screenshot check (LANCE-32).
##   godot --path game res://scenes/portrait_comms_shot.tscn -- --screenshot=out.png [--profile=pmp_flash] [--zoom=3]


func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var profile := String(args.get("profile", "pmp_flash"))
	var sm := SimMission.load_mission(GameData, "mc2_01")
	var mech: SimUnit = sm.world.units.filter(func(x): return x is SimMech)[0]
	mech.pilot_profile = profile
	var kit := HudKit.new(UiStyle.hud_unit(float(get_window().size.y)))
	var bg := ColorRect.new()
	bg.color = Color("#1B2A33")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var row := HBoxContainer.new()
	row.position = Vector2(20, 20)
	row.scale = Vector2.ONE * float(args.get("zoom", 1.0))  # --zoom=3 for a legible capture
	row.add_theme_constant_override("separation", 20)
	add_child(row)
	var lines := [["clean", 0.0, false], ["wounded", 2.0, false], ["dead", 0.0, true]]
	for l in lines:
		var c := CommsWindow.new()
		c.kit = kit
		row.add_child(c)
		mech.pilot.wounds = l[1]
		mech.pilot.dead = l[2]  # a fallen pilot shows the memorial portrait
		c.say(profile.trim_prefix("pmp_").trim_prefix("pmw").to_upper() + " (" + l[0] + ")", "Contact bearing two-seven-zero, closing.", mech, 600.0)
	var tac := CommsWindow.new()
	tac.kit = kit
	row.add_child(tac)
	tac.set_voice(true, "Tac Officer", "Check your tac map for the second tower.")
	for i in 30:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	if args.has("screenshot"):
		get_viewport().get_texture().get_image().save_png(String(args["screenshot"]))
		print("saved ", args["screenshot"])
		get_tree().quit()
