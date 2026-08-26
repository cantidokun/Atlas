from action_plan import ActionSpec
from planning.blender_write_authorization import BlenderWriteAuthorization


def _move() -> ActionSpec:
    return ActionSpec(
        tool="move_object",
        arguments={
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "location": [1, 2, 3],
        },
    )


def test_write_authorization_accepts_registered_verified_write():
    authorization = BlenderWriteAuthorization.issue(_move(), "auth-1")

    assert authorization.tool == "move_object"
    assert authorization.authorization_id == "auth-1"
    assert authorization.matches(_move())


def test_write_authorization_rejects_registered_read_only_capability():
    action = ActionSpec(tool="inspect_scene", arguments={"file_name": "scene.blend"})

    try:
        BlenderWriteAuthorization.issue(action, "auth-read")
    except ValueError as exc:
        assert "verified Blender write capability" in str(exc)
    else:
        raise AssertionError("read-only Blender capability received write authorization")


def test_write_authorization_rejects_unregistered_capability():
    action = ActionSpec(tool="set_value", arguments={"value": 1})

    try:
        BlenderWriteAuthorization.issue(action, "auth-unknown")
    except ValueError as exc:
        assert "verified Blender write capability" in str(exc)
    else:
        raise AssertionError("unknown Blender capability received write authorization")


def test_write_authorization_remains_bound_to_exact_action():
    authorization = BlenderWriteAuthorization.issue(_move(), "auth-2")
    changed = ActionSpec(
        tool="move_object",
        arguments={
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "location": [9, 9, 9],
        },
    )

    assert not authorization.matches(changed)
