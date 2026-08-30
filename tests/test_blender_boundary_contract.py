from planning.blender_execution_boundary import BlenderExecutionBoundary


INSPECT = {"file_name": "test_scene.blend", "object_name": "Goal_Left_post"}


def test_legacy_and_verified_paths_can_coexist():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied"})
    assert boundary.execute("inspect_object_transform", INSPECT)["ok"] is True
    assert boundary.execute_verified("inspect_object_transform", INSPECT).state == "applied"
