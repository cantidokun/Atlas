import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluator


def make_orchestrator():
    evidence = EvidencePlan([
        EvidenceRequest("inspect_object_relationship", {"id": "fixture"}, "relationship")
    ])
    actions = ConditionalActionPlan([
        ActionSpec("move_object", {"id": "left"}, "left"),
        ActionSpec("move_object", {"id": "right"}, "right"),
    ])
    evaluator = TargetStateEvaluator([
        StateInvariant("ready", lambda evidence: evidence["ready"] is True),
    ])
    return ConditionalPlanningOrchestrator(evidence, actions, evaluator)


def test_conditional_orchestrator_snapshot_supports_unsatisfied_target():
    orchestrator = make_orchestrator()
    evidence = orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    result = orchestrator.evaluate_target_state(evidence)

    assert result.satisfied is False
    assert orchestrator.blocked is False
    assert orchestrator.next_phase() == "ACTION"
    snapshot = orchestrator.snapshot()
    assert snapshot["blocked"] is False
    assert snapshot["conditional_actions"]["ready_to_execute"] is True


def test_conditional_orchestrator_blocks_after_action_failure():
    orchestrator = make_orchestrator()
    evidence = orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    orchestrator.evaluate_target_state(evidence)

    with pytest.raises(RuntimeError, match="failure"):
        orchestrator.execute_next_action(lambda tool, args: (_ for _ in ()).throw(RuntimeError("failure")))

    assert orchestrator.blocked is True
    assert orchestrator.next_phase() == "BLOCKED"
    assert orchestrator.snapshot()["conditional_actions"]["action_plan"]["blocked"] is True
