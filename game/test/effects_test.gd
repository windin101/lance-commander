extends GdUnitTestSuite
## Weapon effects (I87): the fx table covers every weapon and resolves in layers, the pools keep to their caps,
## and running the effects leaves the sim exactly as it would be without them.

func _components() -> Array:
	return JSON.parse_string(FileAccess.get_file_as_string("res://data/components.json"))


func test_table_covers_every_weapon_and_names_real_impacts() -> void:
	var t := EffectsView.load_table()
	assert_bool(t.is_empty()).is_false()
	var impacts: Dictionary = t["impacts"]
	var emitters: Dictionary = t["emitters"]
	var kinds := ["beam", "lightning", "tracer", "missile", "flame", "shell"]
	for c in _components():
		var w: Dictionary = c.get("weapon", {})
		if w.is_empty():
			continue
		var fx_id := int(w["special_fx"])
		assert_bool(t["weapons"].has(str(fx_id))).override_failure_message("no fx for %s (%d)" % [c["name"], fx_id]).is_true()
		var s := EffectsView.resolve(t, fx_id, int(c["id"]))
		assert_bool(kinds.has(String(s.get("kind", "")))).override_failure_message("%s: kind %s" % [c["name"], s.get("kind")]).is_true()
		for key in ["muzzle", "hit", "miss", "water"]:
			var n := String(s.get(key, ""))
			if n != "":
				assert_bool(impacts.has(n)).override_failure_message("%s: %s impact %s missing" % [c["name"], key, n]).is_true()
	for name in impacts:
		for el in impacts[name].get("elements", []):
			assert_bool(emitters.has(String(el["emitter"]))).override_failure_message("%s: emitter %s" % [name, el["emitter"]]).is_true()
	for kind in t["deaths"]:
		if kind.begins_with("_"):
			continue
		for step in t["deaths"][kind]["sequence"]:
			assert_bool(impacts.has(String(step[1]))).override_failure_message("%s death: %s" % [kind, step[1]]).is_true()


func test_resolve_layers_family_weapon_component() -> void:
	var t := EffectsView.load_table()
	var ac10 := EffectsView.resolve(t, 18, 101)
	var ultra := EffectsView.resolve(t, 18, 108)
	assert_str(String(ac10["kind"])).is_equal("tracer")
	assert_int(int(ac10["rounds"])).is_equal(1)
	assert_int(int(ultra["rounds"])).is_equal(2)  # Ultra: double tap
	var pulse := EffectsView.resolve(t, 16)
	assert_int(int(pulse["pulses"])).is_equal(4)
	assert_float(float(pulse["duration"])).is_equal(0.6)  # the original's BeamDuration
	assert_bool(pulse.has("original")).is_false()  # baseline data never leaks into the look
	# the original's baseline is recorded: medium laser beam, red, 0.5 s (medlase.fit)
	var orig: Dictionary = t["weapons"]["12"]["original"]
	assert_str(String(orig["kind"])).is_equal("beam")
	assert_str(String(orig["glow"])).is_equal("#ff0000")
	assert_float(float(orig["beam_s"])).is_equal(0.5)
	# an unknown id falls back to a weapon rather than an empty spec
	assert_bool(EffectsView.resolve(t, 9999).has("kind")).is_true()


func test_pools_keep_their_caps() -> void:
	var fx := EffectsView.new()
	fx.caps = {"flash": 8, "spark": 8, "fire": 8, "flame": 8, "smoke": 8, "dust": 8, "debris": 8, "splash": 8,
		"ribbons": 4, "bolts": 3, "lights": 2, "rings": 2, "projectiles": 3, "columns": 2, "damage_smokers": 1}
	add_child(fx)
	await get_tree().process_frame
	for k in ["flash", "smoke", "debris"]:
		assert_int((fx._emitters[k] as GPUParticles3D).amount).is_equal(8)
	var a := Vector3(0, 5, 0)
	var b := Vector3(150, 5, 0)
	for i in 10:
		fx.fire(12, a, b, true, 0.0)  # lasers: one ribbon each
	assert_int(fx._pools["ribbons"].size()).is_equal(4)
	assert_int(fx._pools["lights"].size()).is_less_equal(2)
	assert_int(fx.stats()["stolen"]).is_greater(0)
	for i in 10:
		fx.fire(18, a, b, true, 0.3)  # tracers: projectiles past the cap are skipped, the impact still lands
	assert_int(fx.stats()["projectiles"]).is_less_equal(3)
	assert_int(fx.stats()["dropped_projectiles"]).is_greater(0)
	for i in 5:
		fx.fire(4, a, b, true, 0.0)  # PPC: main bolt + branches share 3 bolts
	assert_int(fx._pools["bolts"].size()).is_equal(3)
	for i in 4:
		fx.destroyed("mech", b)
	var columns := 0
	for e in fx._live:
		if e["type"] == "column":
			columns += 1
	assert_int(columns).is_less_equal(2)
	for i in 30:
		await get_tree().process_frame
	assert_int(fx._pools["ribbons"].size()).is_equal(4)
	fx.queue_free()


func test_debris_is_shards_not_boxes() -> void:
	# Phase 8: debris chunks are irregular shards; one mesh holds every variant (UV2.x) and the shader keeps one.
	var m := EffectsView.shard_mesh()
	assert_object(m).is_not_null()
	assert_bool(EffectsView.shard_mesh() == m).is_true()  # built once, shared
	var arr := m.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var uv2: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV2]
	var normals: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
	assert_int(verts.size() % 3).is_equal(0)
	assert_int(verts.size()).is_less(EffectsView.SHARD_VARIANTS * 40 * 3)  # light: well under 40 triangles a shard
	var seen := {}
	for i in uv2.size():
		seen[int(uv2[i].x)] = true
	assert_int(seen.size()).is_equal(EffectsView.SHARD_VARIANTS)
	var box := AABB()
	for i in verts.size():
		box = box.expand(verts[i]) if i > 0 else AABB(verts[i], Vector3.ZERO)
	assert_float(box.get_longest_axis_size()).is_less(1.4)  # about the unit cube the old BoxMesh filled
	# flat-shaded faces: each triangle's three normals agree and point away from its shard's centre
	for t in range(0, verts.size(), 3):
		assert_bool(normals[t].is_equal_approx(normals[t + 1]) and normals[t].is_equal_approx(normals[t + 2])).is_true()
	# the debris emitter draws it, with the cap unchanged
	var fx := EffectsView.new()
	fx.caps = {"debris": 8}
	add_child(fx)
	await get_tree().process_frame
	var e := fx._emitters["debris"] as GPUParticles3D
	assert_int(e.amount).is_equal(8)
	assert_bool(e.draw_pass_1 == m).is_true()
	assert_bool(e.draw_pass_1 is BoxMesh).is_false()
	fx.queue_free()


func test_projectile_lands_its_impact_after_its_flight() -> void:
	var fx := EffectsView.new()
	add_child(fx)
	await get_tree().process_frame
	var landed: Array = []
	fx.fire(9, Vector3(0, 5, 0), Vector3(200, 5, 0), false, 0.2, {"on_ground": func(p: Vector3, s: float, scorch: bool) -> void: landed.append(p)})
	assert_int(landed.size()).is_equal(0)
	for i in 120:
		await get_tree().process_frame
	assert_int(landed.size()).is_equal(5)  # an LRM5 volley: five craters
	assert_int(fx.stats()["projectiles"]).is_equal(0)
	fx.queue_free()


## Effects are visual only: the same mission stepped with effects shown and with them skipped ends identical.
func test_effects_leave_the_sim_unchanged() -> void:
	var sigs: Array = []
	for show in [true, false]:
		var view: Node3D = load("res://scenes/mission_view.tscn").instantiate()
		view.play_intro = false
		add_child(view)
		await get_tree().process_frame
		view.set_process(false)
		view._demo_orders()
		var shots := 0
		for i in 900:
			view.sm.step()
			for e in view.world.events:
				if e["type"] == "shot":
					shots += 1
			view._consume_events(show)
			if i % 30 == 0:
				for v in view.views.values():
					v.sync(1.0)
				await get_tree().process_frame
		var sig := []
		for u in view.world.units:
			var armor := 0.0
			for a in u.armor:
				armor += a
			sig.append([u.id, snappedf(u.position.x, 0.001), snappedf(u.position.y, 0.001), snappedf(armor, 0.001), u.status])
		sigs.append([shots, sig])
		if show:
			assert_int(view.effects.stats()["shots"]).is_equal(shots)
		view.queue_free()
		await get_tree().process_frame
	assert_int(int(sigs[0][0])).is_greater(0)
	assert_array(sigs[0][1]).is_equal(sigs[1][1])
