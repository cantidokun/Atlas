import json

import pytest
import requests

import live_qwen_object_rotation as rotation
from audit_trail import AuditTrail
from planning.object_rotation_task import TARGET_OBJECT, TARGET_ROTATION


def _plan(file_name):
    return json.dumps(
        {
            "evidence": [
                {
                    "tool": "inspect_object_transform",
                    "arguments": {"file_name": file_name, "object_name": TARGET_OBJECT},
                    "name": "inspect_object_transform",
                }
            ],
            "actions": [
                {
                    "tool": "set_object_rotation",
                    "arguments": {
                        "file_name": file_name,
                        "object_name": TARGET_OBJECT,
                        "rotation_degrees": TARGET_ROTATION,
                    },
                    "name": "set_object_rotation",
                }
            ],
        }
    )


def test_live_rotation_task_definition_uses_typed_evidence_request():
    definition = rotation.object_rotation_task_definition(rotation.CORRECT_FILE)

    assert len(definition.evidence) == 1
    assert definition.evidence[0].tool == "inspect_object_transform"
    assert definition.evidence[0].arguments == {
        "file_name": rotation.CORRECT_FILE,
        "object_name": TARGET_OBJECT,
    }


def test_live_rotation_task_definition_remains_typed_and_deterministic():
    definition = rotation.object_rotation_task_definition(rotation.CORRECT_FILE)

    assert definition.actions[0].tool == "set_object_rotation"
    assert definition.actions[0].arguments == {
        "file_name": rotation.CORRECT_FILE,
        "object_name": TARGET_OBJECT,
        "rotation_degrees": TARGET_ROTATION,
    }
    assert definition.allowed_action_tools == {"set_object_rotation"}
    assert definition.allow_writes is True
    assert definition.verify_after_action is True


def test_rotation_qwen_planning_retries_transient_timeout(monkeypatch):
    responses = [requests.exceptions.ReadTimeout("temporary"), _plan("rotation.blend")]

    def fake_ask(messages):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(rotation, "ask", fake_ask)

    audit = AuditTrail()
    proposal = rotation.build_plan("rotation.blend", audit)

    assert proposal.evidence[0].tool == "inspect_object_transform"
    assert proposal.actions[0].tool == "set_object_rotation"
    assert not responses

    snapshot = audit.snapshot()
    proposal_events = [event for event in snapshot["events"] if event["stage"] == "qwen_proposal"]
    assert len(proposal_events) == 2
    assert proposal_events[0]["status"] == "rejected"
    assert "ReadTimeout" in proposal_events[0]["reason"]
    assert proposal_events[1]["status"] == "accepted"


def test_rotation_qwen_planning_fails_closed_after_three_timeouts(monkeypatch):
    def always_timeout(messages):
        raise requests.exceptions.ReadTimeout("persistent")

    monkeypatch.setattr(rotation, "ask", always_timeout)

    with pytest.raises(RuntimeError, match="timed out after 3 attempts"):
        rotation.build_plan("rotation.blend", AuditTrail())
