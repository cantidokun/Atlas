import pytest

from planning.action_plan import ActionSpec
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_write_authorization import BlenderWriteAuthorization


def _action():
    return ActionSpec("move_object", {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]})


def _authorization():
    return BlenderWriteAuthorization.issue(_action(), "journal-auth")


def _receipt():
    action = _action()
    result = BlenderExecutionResult("move_object", True, "moved", {"mutation_performed": True})
    return BlenderExecutionReceipt.create_authorized(
        action.tool, action.arguments, result, "journal-auth"
    )


def test_journal_records_started_attempt_and_survives_restart(tmp_path):
    database = tmp_path / "execution-journal.sqlite3"
    action = _action()
    authorization = _authorization()

    first = SQLiteBlenderExecutionJournal(str(database))
    assert first.begin(action, authorization) is True
    started = first.get("journal-auth")
    assert started["status"] == "STARTED"
    first.close()

    second = SQLiteBlenderExecutionJournal(str(database))
    assert second.begin(action, authorization) is False
    assert second.get("journal-auth")["status"] == "STARTED"
    second.close()


def test_journal_completion_persists_receipt_and_outcome(tmp_path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "journal.sqlite3"))
    authorization = _authorization()
    assert journal.begin(_action(), authorization) is True

    journal.complete(authorization, _receipt(), "VERIFIED")
    record = journal.get("journal-auth")

    assert record["status"] == "COMPLETED"
    assert record["outcome_status"] == "VERIFIED"
    assert record["receipt_digest"] == _receipt().result_digest
    assert record["completed_at"] is not None
    journal.close()


def test_journal_rejects_mismatched_authorization(tmp_path):
    journal = SQLiteBlenderExecutionJournal(str(tmp_path / "journal.sqlite3"))
    other = BlenderWriteAuthorization.issue(
        ActionSpec("move_object", {"file_name": "scene.blend", "object_name": "Other", "location": [1, 2, 3]}),
        "journal-other",
    )
    with pytest.raises(ValueError, match="does not match action"):
        journal.begin(_action(), other)
    journal.close()
