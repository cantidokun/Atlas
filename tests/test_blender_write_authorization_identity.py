import pytest

from planning.action_plan import ActionSpec
from planning.blender_write_authorization import BlenderWriteAuthorization


def test_authorization_identity_is_required_and_preserved():
    action = ActionSpec(
        tool="move_object",
        arguments={"object_name": "Cube", "location": [1, 2, 3]},
    )

    authorization = BlenderWriteAuthorization.issue(action, "auth-123")

    assert authorization.authorization_id == "auth-123"
    assert authorization.snapshot()["authorization_id"] == "auth-123"
    assert authorization.matches(action)


def test_empty_authorization_identity_is_rejected():
    action = ActionSpec(
        tool="move_object",
        arguments={"object_name": "Cube", "location": [1, 2, 3]},
    )

    with pytest.raises((ValueError, TypeError)):
        BlenderWriteAuthorization.issue(action, "")


def test_authorization_identity_is_normalized_before_receipt_binding():
    action = ActionSpec(
        tool="move_object",
        arguments={"object_name": "Cube", "location": [1, 2, 3]},
    )

    authorization = BlenderWriteAuthorization.issue(action, "  auth-123  ")

    assert authorization.authorization_id == "auth-123"
    assert authorization.action_authorization.authorization_id == "auth-123"
