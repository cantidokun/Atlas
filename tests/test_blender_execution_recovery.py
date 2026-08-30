from pathlib import Path

import pytest

from planning.action_plan import ActionSpec
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery
from planning.blender_write_authorization import BlenderWriteAuthorization


def _action():
    return ActionSpec("move_object", {"object_name": "Ball", "location": [1.0, 2.0, 3.0]})


def _authorization():
    return BlenderWriteAuthorization.issue(_action(), "auth-recovery-1")


def test_recovery_verifies_started_execution_without_replaying_write(tmp_path: Path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "journal.sqlite"))
    action = _action()
    authorization = _authorization()
    assert journal.begin(action, authorization) is True
    calls = []

    recovery = BlenderExecutionRecovery(journal)
    outcome = recovery.reconcile(
        action,
        authorization,
        lambda recovered_action, record: (calls.append((recovered_action, record)) or (True, {"scene_matches": True})),
    )

    assert outcome["status"] == "VERIFIED"
    assert outcome["recovered"] is True
    assert len(calls) == 1
    assert journal.get(authorization.authorization_id)["status"] == "COMPLETED"
    assert journal.get(authorization.authorization_id)["outcome_status"] == "VERIFIED"
    journal.close()


def test_recovery_blocks_when_authoritative_state_does_not_match(tmp_path: Path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "journal.sqlite"))
    action = _action()
    authorization = _authorization()
    assert journal.begin(action, authorization) is True

    outcome = BlenderExecutionRecovery(journal).reconcile(
        action, authorization, lambda _action, _record: (False, {"scene_matches": False})
    )

    assert outcome == {"status": "BLOCKED", "recovered": False, "scene_matches": False}
    assert journal.get(authorization.authorization_id)["outcome_status"] == "BLOCKED"
    journal.close()


def test_recovery_rejects_argument_identity_mismatch(tmp_path: Path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "journal.sqlite"))
    action = _action()
    authorization = _authorization()
    assert journal.begin(action, authorization) is True
    altered = ActionSpec("move_object", {"object_name": "Ball", "location": [9.0, 9.0, 9.0]})

    with pytest.raises(RuntimeError, match="arguments do not match"):
        BlenderExecutionRecovery(journal).reconcile(altered, authorization, lambda *_: (True, {}))
    journal.close()


def test_recovery_never_replays_terminal_execution(tmp_path: Path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "journal.sqlite"))
    action = _action()
    authorization = _authorization()
    assert journal.begin(action, authorization) is True
    journal.complete(authorization, None, "VERIFIED")

    with pytest.raises(RuntimeError, match="not interrupted"):
        BlenderExecutionRecovery(journal).reconcile(action, authorization, lambda *_: (True, {}))
    journal.close()
