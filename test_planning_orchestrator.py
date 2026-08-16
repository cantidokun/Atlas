"""Tests for the Atlas planning orchestrator."""

import pytest

from action_plan import ActionPlan, ActionSpec
from evidence_plan import EvidencePlan, EvidenceRequest
from planning_orchestrator import PlanningOrchestrator


def _orchestrator():
    evidence = EvidencePlan(
        requests=[EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene")]
    )
    actions = ActionPlan(
        actions=[ActionSpec("move_object", {"object_name": "A", "location": [1, 0, 0]}, "move")]
    )
    return PlanningOrchestrator(evidence, actions)


def test_starts_in_evidence_phase():
    orchestrator = _orchestrator()
    assert orchestrator.next_phase() == "EVIDENCE"


def test_action_is_blocked_until_evidence_is_complete():
    orchestrator = _orchestrator()
    with pytest.raises(RuntimeError, match="evidence"):
        orchestrator.execute_next_action(lambda tool, args: {})


def test_reused_evidence_unlocks_action_phase():
    orchestrator = _orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: {}, reused_result={"objects": 2})
    assert orchestrator.next_phase() == "ACTION"


def test_missing_evidence_is_executed_then_action_runs():
    orchestrator = _orchestrator()
    calls = []

    def execute(tool, args):
        calls.append(tool)
        if tool == "inspect_scene":
            return {"objects": 2}
        return {"status": "moved"}

    orchestrator.acquire_next_evidence(execute)
    orchestrator.execute_next_action(execute)

    assert calls == ["inspect_scene", "move_object"]
    assert orchestrator.next_phase() == "COMPLETE"


def test_failed_evidence_blocks_action_phase():
    orchestrator = _orchestrator()
    orchestrator.acquire_next_evidence(
        lambda tool, args: {"error": "inspection failed"}
    )
    assert orchestrator.blocked
    assert orchestrator.next_phase() == "BLOCKED"
