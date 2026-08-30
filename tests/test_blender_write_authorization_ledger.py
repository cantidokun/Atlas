import pytest

from planning.action_plan import ActionSpec
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.blender_write_authorization_ledger import BlenderWriteAuthorizationLedger


def _authorization() -> BlenderWriteAuthorization:
    action = ActionSpec(tool="delete_object", arguments={"name": "Cube"})
    return BlenderWriteAuthorization.issue(action, "auth-123")


def test_authorization_is_single_use():
    ledger = BlenderWriteAuthorizationLedger()
    authorization = _authorization()

    assert ledger.consume(authorization) is True
    assert ledger.is_consumed(authorization) is True
    assert ledger.consume(authorization) is False


def test_different_authorization_ids_are_independently_consumable():
    ledger = BlenderWriteAuthorizationLedger()
    first = _authorization()
    action = ActionSpec(tool="delete_object", arguments={"name": "Cube"})
    second = BlenderWriteAuthorization.issue(action, "auth-456")

    assert ledger.consume(first) is True
    assert ledger.consume(second) is True


def test_ledger_rejects_invalid_authorization_type():
    ledger = BlenderWriteAuthorizationLedger()

    with pytest.raises(TypeError):
        ledger.consume(object())
