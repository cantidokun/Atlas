"""Tests for generic Atlas evidence-plan primitives."""

import pytest

from evidence_plan import EvidencePlan, EvidenceRequest


def _plan():
    return EvidencePlan(
        requests=[
            EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene"),
            EvidenceRequest(
                "inspect_object_relationship",
                {"object1_name": "A", "object2_name": "B"},
                "relationship",
            ),
        ]
    )


def test_plan_starts_with_first_request():
    plan = _plan()
    assert plan.next_request.name == "scene"
    assert not plan.complete


def test_success_advances_to_next_request():
    plan = _plan()
    plan.record_result({"objects": 2}, True)
    assert plan.current_index == 1
    assert plan.next_request.name == "relationship"


def test_reused_evidence_advances_without_new_execution():
    plan = _plan()
    plan.record_result({"objects": 2}, True, reused=True)
    assert plan.current_index == 1
    assert plan.skipped[0]["reused"] is True


def test_failure_blocks_plan():
    plan = _plan()
    plan.record_result({"error": "inspection failed"}, False)
    assert plan.blocked
    assert plan.next_request is None


def test_plan_completes_after_all_evidence_is_known():
    plan = _plan()
    plan.record_result({"objects": 2}, True, reused=True)
    plan.record_result({"midpoint": [0.0, 0.0, 0.0]}, True)
    assert plan.complete
    assert plan.snapshot()["current_index"] == 2


def test_completed_plan_cannot_be_advanced():
    plan = _plan()
    plan.record_result({}, True)
    plan.record_result({}, True)
    with pytest.raises(RuntimeError, match="already complete"):
        plan.record_result({}, True)
