import pytest

from planning.action_plan import ActionSpec
from planning.blender_write_authorization import BlenderWriteAuthorization


def test_write_authorization_accepts_registered_write_capability():
    action = ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )
    authorization = BlenderWriteAuthorization.issue(action, "auth-1")
    assert authorization.matches(action)
    assert authorization.snapshot()["tool"] == "move_object"


def test_write_authorization_rejects_read_only_capability():
    action = ActionSpec(
        tool="inspect_scene",
        arguments={"file_name": "scene.blend"},
    )
    with pytest.raises(ValueError, match="scene-writing capability"):
        BlenderWriteAuthorization.issue(action, "auth-2")


def test_write_authorization_rejects_changed_action():
    action = ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )
    changed = ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [4, 5, 6]},
    )
    authorization = BlenderWriteAuthorization.issue(action, "auth-3")
    assert not authorization.matches(changed)
