extends GdUnitTestSuite


func test_argb_from_signed_fit_value() -> void:
	assert_object(MechPaint.argb(-16711936)).is_equal(Color8(0, 255, 0))  # 0xFF00FF00
	assert_object(MechPaint.argb(-1944008)).is_equal(Color8(0xE2, 0x56, 0x38))


func test_pure_channels_take_scheme_colours_others_untouched() -> void:
	var mask := Image.create(4, 1, false, Image.FORMAT_RGBA8)
	mask.set_pixel(0, 0, Color8(255, 0, 0))
	mask.set_pixel(1, 0, Color8(0, 128, 0))
	mask.set_pixel(2, 0, Color8(0, 0, 64))
	mask.set_pixel(3, 0, Color8(90, 90, 90))  # painted detail stays
	var red := Color8(200, 100, 50)
	var out := MechPaint.recolor(mask, red, Color8(10, 250, 10), Color8(255, 255, 255))
	var k := 1.0 - pow(1.0 - 255.0 / 256.0, 2)
	assert_int(out.get_pixel(0, 0).r8).is_equal(int(200 * k))
	assert_int(out.get_pixel(0, 0).g8).is_equal(int(100 * k))
	var kg := 1.0 - pow(1.0 - 128.0 / 256.0, 2)  # 0.75
	assert_int(out.get_pixel(1, 0).g8).is_equal(int(250 * kg))
	var kb := 1.0 - pow(1.0 - 64.0 / 256.0, 2)
	assert_int(out.get_pixel(2, 0).b8).is_equal(int(255 * kb))
	assert_object(out.get_pixel(3, 0)).is_equal(Color8(90, 90, 90))


func test_real_masks_load_for_slice_mechs() -> void:
	for m in ["bushwacker", "werewolf", "starslayer", "urbanmech"]:
		var mask := MechPaint.load_mask(m)
		assert_object(mask).is_not_null()
		assert_int(mask.get_width()).is_greater(0)
