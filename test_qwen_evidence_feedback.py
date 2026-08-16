import json

import pytest

from qwen_evidence_feedback import build_evidence_message, evidence_summary


def test_builds_bounded_evidence_message():
    message = build_evidence_message([
        {"tool": "inspect_scene", "result": {"scene": "Scene", "total_objects": 6}},
    ])

    assert message["role"] == "user"
    assert message["content"].startswith("ATLAS_VERIFIED_EVIDENCE:")
    assert '"total_objects":6' in message["content"]
    assert "Do not claim facts not present in it" in message["content"]


def test_feedback_is_json_serializable():
    message = build_evidence_message([
        {"tool": "inspect_scene", "result": {"objects": ["Cube"]}},
    ])
    json.dumps(message)


def test_rejects_malformed_results():
    with pytest.raises(ValueError):
        build_evidence_message([{"tool": "inspect_scene"}])


def test_summary_is_deterministic():
    assert evidence_summary([
        {"tool": "inspect_scene", "result": {}},
        {"tool": "inspect_object_relationship", "result": {}},
    ]) == {
        "evidence_count": 2,
        "tools": ["inspect_scene", "inspect_object_relationship"],
    }
