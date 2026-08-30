"""Fresh-runtime persistence tests for autonomous Blender admission."""

from planning.action_plan import ActionSpec
from planning.blender_autonomous_admission import BlenderAutonomousAdmission
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


def _action():
    return ActionSpec(tool="move_object", arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]})


def test_unresolved_execution_survives_fresh_runtime_and_is_reconciled(tmp_path):
    database = str(tmp_path / "atlas.db")
    action = _action()
    authorization = BlenderWriteAuthorization.issue(action, "restart-auth")

    first_journal = SQLiteBlenderExecutionJournal(database)
    assert first_journal.begin(action, authorization) is True
    first_journal.close()

    second_journal = SQLiteBlenderExecutionJournal(database)
    second_admission = BlenderAutonomousAdmission(
        BlenderLiveWriteGate(), second_journal, BlenderExecutionRecovery(second_journal)
    )
    assert second_admission.ready is False

    results = second_admission.startup(lambda recovered_action, record: (True, {"authoritative": True}))
    assert results == [{"status": "VERIFIED", "recovered": True, "authoritative": True}]
    assert second_admission.ready is True
    second_journal.close()
