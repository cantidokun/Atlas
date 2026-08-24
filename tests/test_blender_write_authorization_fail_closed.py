import pytest

from planning.action_plan import ActionSpec
from planning.blender_write_authorization import BlenderWriteAuthorization


def test_read_capability_cannot_receive_write_authorization():
    action = ActionSpec(tool="inspect_object_transform", arguments={"object_name": "Cube"})
    with pytest.raises(ValueError, match="scene-writing capability"):
        BlenderWriteAuthorization.issue(action, "read-is-not-write")


def test_unknown_capability_cannot_receive_write_authorization():
    action = ActionSpec(tool="unknown_blender_capability", arguments={})
    with pytest.raises(ValueError, match="Unknown Blender capability"):
        BlenderWriteAuthorization.issue(action, "unknown-is-not-write")
