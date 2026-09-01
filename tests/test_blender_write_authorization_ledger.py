import pytest

from planning.action_plan import ActionSpec
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.blender_write_authorization_ledger import (
    BlenderWriteAuthorizationLedger,
    SQLiteBlenderWriteAuthorizationLedger,
)


def _authorization(authorization_id="auth-123") -> BlenderWriteAuthorization:
    action = ActionSpec(tool="delete_object", arguments={"name": "Cube"})
    return BlenderWriteAuthorization.issue(action, authorization_id)


def test_authorization_is_single_use():
    ledger = BlenderWriteAuthorizationLedger()
    authorization = _authorization()

    assert ledger.consume(authorization) is True
    assert ledger.is_consumed(authorization) is True
    assert ledger.consume(authorization) is False


def test_different_authorization_ids_are_independently_consumable():
    ledger = BlenderWriteAuthorizationLedger()
    first = _authorization("auth-123")
    second = _authorization("auth-456")

    assert ledger.consume(first) is True
    assert ledger.consume(second) is True


def test_ledger_rejects_invalid_authorization_type():
    ledger = BlenderWriteAuthorizationLedger()

    with pytest.raises(TypeError):
        ledger.consume(object())


def test_sqlite_ledger_survives_process_lifecycle(tmp_path):
    database = tmp_path / "authorization-ledger.sqlite3"
    authorization = _authorization("persistent-auth")

    first = SQLiteBlenderWriteAuthorizationLedger(str(database))
    assert first.consume(authorization) is True
    first.close()

    second = SQLiteBlenderWriteAuthorizationLedger(str(database))
    assert second.is_consumed(authorization) is True
    assert second.consume(authorization) is False
    second.close()


def test_sqlite_ledger_rejects_invalid_authorization_type(tmp_path):
    ledger = SQLiteBlenderWriteAuthorizationLedger(str(tmp_path / "ledger.sqlite3"))
    try:
        with pytest.raises(TypeError):
            ledger.consume(object())
    finally:
        ledger.close()
