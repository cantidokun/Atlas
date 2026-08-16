from action_plan import ActionSpec, ActionPlan
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.planning_orchestrator import ConditionalPlanningOrchestrator, PlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _evidence_plan():
    return EvidencePlan([EvidenceRequest("inspect", {"id": 1}, "inspect")])


def _evaluator():
    return TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])


def test_evidence_executor_exception_blocks_generic_orchestrator():
    orchestrator = PlanningOrchestrator(
        evidence_plan=_evidence_plan(),
        action_plan=ActionPlan([]),
    )

    def fail(_tool, _arguments):
        raise RuntimeError("evidence unavailable")

    try:
        orchestrator.acquire_next_evidence(fail)
    except RuntimeError as exc:
        assert str(exc) == "evidence unavailable"
    else:
        raise AssertionError("expected evidence executor failure")

    assert orchestrator.evidence_plan.blocked
    assert orchestrator.next_phase() == "BLOCKED"


def test_action_executor_exception_blocks_generic_orchestrator():
    orchestrator = PlanningOrchestrator(
        evidence_plan=EvidencePlan([]),
        action_plan=ActionPlan([ActionSpec("write", {}, "write")]),
    )

    def fail(_tool, _arguments):
        raise RuntimeError("write unavailable")

    try:
        orchestrator.execute_next_action(fail)
    except RuntimeError as exc:
        assert str(exc) == "write unavailable"
    else:
        raise AssertionError("expected action executor failure")

    assert orchestrator.action_plan.blocked
    assert orchestrator.next_phase() == "BLOCKED"


def test_conditional_action_executor_exception_blocks_orchestrator():
    orchestrator = ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan([EvidenceRequest("inspect", {}, "inspect")]),
        conditional_plan=ConditionalActionPlan([ActionSpec("write", {}, "write")]),
        target_evaluator=_evaluator(),
    )
    orchestrator.acquire_next_evidence(lambda _tool, _arguments: {"ready": False})
    result = orchestrator.evaluate_target_state({"ready": False})
    assert result.satisfied is False

    def fail(_tool, _arguments):
        raise RuntimeError("conditional write unavailable")

    try:
        orchestrator.execute_next_action(fail)
    except RuntimeError as exc:
        assert str(exc) == "conditional write unavailable"
    else:
        raise AssertionError("expected conditional action executor failure")

    assert orchestrator.conditional_plan.blocked
    assert orchestrator.next_phase() == "BLOCKED"
