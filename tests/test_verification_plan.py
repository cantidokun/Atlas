import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.verification_plan import VerificationPlan


def make_evaluator():
    return TargetStateEvaluator([
        StateInvariant("ready", lambda evidence: evidence.get("ready") is True),
    ])


def make_orchestrator():
    evidence = EvidencePlan([
        EvidenceRequest(tool="inspect_state", arguments={}),
    ])
    actions = ConditionalActionPlan([
        ActionSpec(tool="write_state", arguments={"value": "target"}, name="write target"),
    ])
    return ConditionalPlanningOrchestrator(
        evidence_plan=evidence,
        conditional_plan=actions,
        target_evaluator=make_evaluator(),
        verification_plan=VerificationPlan(make_evaluator()),
    )


def test_verification_is_a_distinct_phase_after_action():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    orchestrator.evaluate_target_state({"ready": False})
    assert orchestrator.next_phase() == "AUTHORIZATION"
    orchestrator.authorize_execution("verification-phase-test")
    assert orchestrator.next_phase() == "ACTION"

    orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})
    assert orchestrator.next_phase() == "VERIFICATION"
    assert not orchestrator.verification_complete

    result = orchestrator.verify_post_action({"ready": True})
    assert result.satisfied is True
    assert orchestrator.next_phase() == "COMPLETE"


def test_successful_write_does_not_count_as_verification():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": False})
    orchestrator.evaluate_target_state({"ready": False})
    orchestrator.authorize_execution("verification-success-test")
    orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})

    assert orchestrator.action_complete
    assert not orchestrator.verification_complete
    result = orchestrator.verify_post_action({"ready": False})
    assert result.satisfied is False
    assert orchestrator.blocked
    assert orchestrator.next_phase() == "BLOCKED"


def test_already_correct_path_requires_fresh_verification_before_complete():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: {"ready": True})
    orchestrator.evaluate_target_state({"ready": True})

    assert orchestrator.skipped
    assert orchestrator.next_phase() == "VERIFICATION"
    with pytest.raises(RuntimeError, match="already satisfied"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})

    result = orchestrator.verify_post_action({"ready": True})
    assert result.satisfied is True
    assert orchestrator.next_phase() == "COMPLETE"


def test_verification_failure_fails_closed():
    plan = VerificationPlan(make_evaluator())
    result = plan.verify({"ready": False})
    assert result.satisfied is False
    assert plan.blocked
    assert not plan.complete
