from planning.blender_execution_boundary import BlenderExecutionBoundary


def test_legacy_and_verified_paths_can_coexist():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied"})
    assert boundary.execute("inspect_object", {"object_name": "Goal_Left_post"})["ok"] is True
    assert boundary.execute_verified("inspect_object", {"object_name": "Goal_Left_post"}).state == "applied"
