from tools.blender_test_fixture import create_test_object, set_test_transform


def test_fixture_module_exports_isolated_helpers():
    assert callable(create_test_object)
    assert callable(set_test_transform)
