"""End-to-end tests for the autonomous Blender admission boundary."""

import pytest

from planning.action_plan import ActionSpec
from planning.blender_autonomous_admission import BlenderAutonomousAdmission
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_write_authorization import BlenderWriteAuthorization


class FakeBoundary:
    def __init__(self, action, authorization):
        self.action = action
        self.authorization = authorization
        self.calls = 0

    def execute_authorized_write(self, action, authorization):
        self.calls += 1
        result = BlenderExecutionResult(
            tool=action.tool,
            ok=True,
            state="moved",
            details={"mutation_performed": True},
        )
        receipt = BlenderExecutionReceipt.create_authorized(
            action.tool,
            action.arguments,
            result,
            authorization.authorization_id,
        )
        return result, receipt


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def _authorization():
    return BlenderWriteAuthorization.issue(_action(), "autonomous-test-authorization")


def _admission(tmp_path, action=None, authorization=None):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "atlas.db"))
    recovery = BlenderExecutionRecovery(journal)
    action = action or _action()
    authorization = authorization or BlenderWriteAuthorization.issue(action, "autonomous-test-authorization")
    boundary = FakeBoundary(action, authorization)
    gate = BlenderLiveWriteGate(
        boundary,
        lambda _action, _receipt: (True, {"authoritative": True}),
        execution_journal=journal,
    )
    return BlenderAutonomousAdmission(gate, journal, recovery), journal, boundary, action, authorization


def test_autonomous_execution_is_locked_until_startup_reconciliation(tmp_path):
    admission, journal, boundary, action, authorization = _admission(tmp_path)

    with pytest.raises(RuntimeError, match="locked pending startup reconciliation"):
        admission.execute(action, authorization)
    assert boundary.calls == 0
    journal.close()


def test_clean_startup_unlocks_autonomous_execution(tmp_path):
    admission, journal, boundary, action, authorization = _admission(tmp_path)

    assert admission.startup(lambda _action, _record: (True, {"source": "authoritative-test"})) == []
    assert admission.ready is True
    outcome = admission.execute(action, authorization)
    assert outcome.status == "VERIFIED"
    assert boundary.calls == 1
    journal.close()


def test_unresolved_execution_must_reconcile_before_unlock(tmp_path):
    admission, journal, boundary, action, authorization = _admission(tmp_path)
    assert journal.begin(action, authorization) is True
    assert admission.ready is False

    results = admission.startup(lambda _action, _record: (True, {"recovered": True}))
    assert results == [{"status": "VERIFIED", "recovered": True}]
    assert admission.ready is True
    journal.close()


def test_failed_reconciliation_keeps_autonomous_execution_locked(tmp_path):
    admission, journal, boundary, action, authorization = _admission(tmp_path)
    assert journal.begin(action, authorization) is True

    results = admission.startup(lambda _action, _record: (False, {"reason": "scene state unavailable"}))

    assert results == [{"status": "BLOCKED", "recovered": False, "reason": "scene state unavailable"}]
    assert admission.ready is False
    with pytest.raises(RuntimeError, match="locked pending startup reconciliation"):
        admission.execute(action, authorization)
    assert boundary.calls == 0
    journal.close()
