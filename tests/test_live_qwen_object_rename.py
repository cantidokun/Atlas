import json

import pytest
import requests

import live_qwen_object_rename as rename
from audit_trail import AuditTrail
from planning.object_rename_task import TARGET_NAME, TARGET_OBJECT


def _plan(file_name):
    return json.dumps(
        {
            "evidence": [
                {
                    "tool": "inspect_scene",
                    "arguments": {"file_name": file_name},
                    "name": "inspect_scene",
                }
            ],
            "actions": [
                {
                    "tool": "rename_object",
                    "arguments": {
                        "file_name": file_name,
                        "object_name": TARGET_OBJECT,
                        "new_name": TARGET_NAME,
                    },
                    "name": "rename_object",
                }
            ],
        }
    )


def test_rename_qwen_planning_retries_transient_timeout(monkeypatch):
    responses = [requests.exceptions.ReadTimeout("temporary"), _plan("rename.blend")]

    def fake_ask(messages):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(rename, "ask", fake_ask)

    audit = AuditTrail()
    proposal = rename.build_plan("rename.blend", audit)

    assert proposal.evidence[0].tool == "inspect_scene"
    assert proposal.actions[0].tool == "rename_object"
    assert not responses

    snapshot = audit.snapshot()
    proposal_events = [event for event in snapshot["events"] if event["stage"] == "qwen_proposal"]
    assert len(proposal_events) == 2
    assert proposal_events[0]["status"] == "rejected"
    assert "ReadTimeout" in proposal_events[0]["reason"]
    assert proposal_events[1]["status"] == "accepted"


def test_rename_qwen_planning_fails_closed_after_three_timeouts(monkeypatch):
    def always_timeout(messages):
        raise requests.exceptions.ReadTimeout("persistent")

    monkeypatch.setattr(rename, "ask", always_timeout)

    with pytest.raises(RuntimeError, match="timed out after 3 attempts"):
        rename.build_plan("rename.blend", AuditTrail())
