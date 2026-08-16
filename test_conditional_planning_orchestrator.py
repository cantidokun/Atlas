import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluationError, TargetStateEvaluator

ACTIONS = [
    ActionSpec(
        tool="move_object",
        arguments={"object_name": "A", "location": [1, 0, 0]},
        name="move",
    )
]


def make_orchestrator():
    evidence = EvidencePlan([
        EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene")
    ])
    conditional = ConditionalActionPlan(ACTIONS)
    evaluator = TargetStateEvaluator([
        StateInvariant("ready", lambda evidence: evidence["ready"] is True)
    ])
    return ConditionalPlanningOrchestrator(evidence, conditional, evaluator)


def test_action_is_blocked_until_evidence_and_target_evaluation():
    orchestrator = make_orchestrator()
    with pytest.raises(RuntimeError, match="evidence"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    assert orchestrator.next_phase() == "TARGET_EVALUATION"
    with pytest.raises(RuntimeError, match="target state"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})


def test_satisfied_target_skips_action_without_execution():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": True})
    result = orchestrator.evaluate_target_state({"ready": True})
    assert result.satisfied is True
    assert orchestrator.skipped is True
    assert orchestrator.next_phase() == "COMPLETE"
    with pytest.raises(RuntimeError, match="skipped"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})


def test_unsatisfied_target_exposes_action_and_executes_in_order():
    orchestrator = make_orchestrator()
    calls = []
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    result = orchestrator.evaluate_target_state({"ready": False})
    assert result.satisfied is False
    assert orchestrator.next_phase() == "ACTION"

    def execute(tool, args):
        calls.append((tool, args))
        return {"status": "moved"}

    assert orchestrator.execute_next_action(execute)["status"] == "moved"
    assert calls == [("move_object", {"object_name": "A", "location": [1, 0, 0]})]
    assert orchestrator.next_phase() == "COMPLETE"


def test_target_evaluation_failure_blocks_execution():
    evidence = EvidencePlan([
        EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene")
    ])
    conditional = ConditionalActionPlan(ACTIONS)
    evaluator = TargetStateEvaluator([
        StateInvariant("required", lambda evidence: evidence["missing"] == 1)
    ])
    orchestrator = ConditionalPlanningOrchestrator(evidence, conditional, evaluator)
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    with pytest.raises(TargetStateEvaluationError, match="could not be evaluated"):
        orchestrator.evaluate_target_state({"ready": False})
    assert orchestrator.blocked is True
    assert orchestrator.next_phase() == "BLOCKED"
    with pytest.raises(RuntimeError, match="blocked"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})


def test_target_state_cannot_be_evaluated_twice():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": True})
    orchestrator.evaluate_target_state({"ready": True})
    with pytest.raises(RuntimeError, match="already been evaluated"):
        orchestrator.evaluate_target_state({"ready": True})
