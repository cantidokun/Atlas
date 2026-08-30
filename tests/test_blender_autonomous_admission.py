"""End-to-end tests for the autonomous Blender admission boundary."""

import pytest

from planning.action_plan import ActionSpec
from planning.blender_autonomous_admission import BlenderAutonomousAdmission
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


def _action():
    return ActionSpec(tool="blender.create_object", arguments={"name": "Cube"})


def _authorization():
    return BlenderWriteAuthorization.issue(_action(), "autonomous-test-authorization")


def test_autonomous_execution_is_locked_until_startup_reconciliation(tmp_path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "atlas.db"))
    gate = BlenderLiveWriteGate()
    admission = BlenderAutonomousAdmission(gate, journal, BlenderExecutionRecovery(journal))

    with pytest.raises(RuntimeError, match="locked pending startup reconciliation"):
        admission.execute(_action(), _authorization())


def test_clean_startup_unlocks_autonomous_execution(tmp_path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "atlas.db"))
    gate = BlenderLiveWriteGate()
    admission = BlenderAutonomousAdmission(gate, journal, BlenderExecutionRecovery(journal))

    assert admission.startup(lambda action, record: (True, {"source": "authoritative-test"})) == []
    assert admission.ready is True


def test_unresolved_execution_must_reconcile_before_unlock(tmp_path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "atlas.db"))
    action = _action()
    authorization = _authorization()
    assert journal.begin(action, authorization) is True

    gate = BlenderLiveWriteGate()
    admission = BlenderAutonomousAdmission(gate, journal, BlenderExecutionRecovery(journal))
    assert admission.ready is False

    results = admission.startup(lambda recovered_action, record: (True, {"recovered": True}))
    assert results == [{"status": "VERIFIED", "recovered": True}]
    assert admission.ready is True


def test_failed_reconciliation_keeps_autonomous_execution_locked(tmp_path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "atlas.db"))
    authorization = _authorization()
    assert journal.begin(_action(), authorization) is True

    gate = BlenderLiveWriteGate()
    admission = BlenderAutonomousAdmission(gate, journal, BlenderExecutionRecovery(journal))
    results = admission.startup(lambda action, record: (False, {"reason": "scene state unavailable"}))

    assert results == [{"status": "BLOCKED", "recovered": False, "reason": "scene state unavailable"}]
    assert admission.ready is True
