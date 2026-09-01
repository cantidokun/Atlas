"""Verify a fresh authorization can resume after restart recovery."""

from planning.action_plan import ActionSpec
from planning.blender_autonomous_admission import BlenderAutonomousAdmission
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


class RecordingBoundary(BlenderExecutionBoundary):
    def __init__(self):
        self.calls = []

    def execute_authorized_write(self, action, authorization):
        self.calls.append((action, authorization.authorization_id))
        raise RuntimeError("boundary execution failed")


def _action(name):
    return ActionSpec(tool="move_object", arguments={"file_name": "scene.blend", "object_name": name, "location": [1, 2, 3]})


def test_fresh_authorization_is_distinct_after_recovery(tmp_path):
    database = str(tmp_path / "atlas.db")
    old_action = _action("Cube")
    old_auth = BlenderWriteAuthorization.issue(old_action, "recovered-auth")

    journal = SQLiteBlenderExecutionJournal(database)
    assert journal.begin(old_action, old_auth) is True
    journal.close()

    journal = SQLiteBlenderExecutionJournal(database)
    boundary = RecordingBoundary()
    admission = BlenderAutonomousAdmission(
        BlenderLiveWriteGate(boundary, execution_journal=journal),
        journal,
        BlenderExecutionRecovery(journal),
    )
    results = admission.startup(lambda action, record: (True, {"recovered": True}))
    assert results[0]["status"] == "VERIFIED"
    assert admission.ready is True

    new_action = _action("Ball")
    new_auth = BlenderWriteAuthorization.issue(new_action, "fresh-auth")
    assert new_auth.authorization_id != old_auth.authorization_id
    assert new_auth.matches(new_action)

    result = admission.execute(new_action, new_auth)
    assert result.status == "BLOCKED"
    assert result.reason == "Blender execution failed closed"

    record = journal.get(new_auth.authorization_id)
    assert record is not None
    assert record["status"] == "COMPLETED"
    assert record["outcome_status"] == "BLOCKED"
    assert record["error_type"] == "RuntimeError"
    assert boundary.calls == [(new_action, "fresh-auth")]
    journal.close()
