extends GdUnitTestSuite


func test_engine_runs() -> void:
	assert_int(Engine.get_version_info().major).is_equal(4)
