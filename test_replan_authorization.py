import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.replan_authorization import ReplanAuthorization
from planning.target_state import StateInvariant, TargetStateEvaluator


def _orchestrator():
    evaluator = TargetStateEvaluator([
        StateInvariant("ready", lambda evidence: evidence["ready"] is True)
    ])
    evidence = EvidencePlan([
        EvidenceRequest("inspect", {}, "inspect")
    ])
    actions = ConditionalActionPlan([
        ActionSpec("write", {"value": 1}, "write")
    ])
    return ConditionalPlanningOrchestrator(evidence, actions, evaluator)


def _failed_orchestrator():
    orchestrator = _orchestrator()
    orchestrator.acquire_next_evidence(lambda _tool, _args: {"ready": False})
    orchestrator.evaluate_target_state({"ready": False})
    with pytest.raises(RuntimeError, match="write failed"):
        orchestrator.execute_next_action(
            lambda _tool, _args: (_ for _ in ()).throw(RuntimeError("write failed"))
        )
    orchestrator.record_recovery_evidence({"ready": False, "revision": 2})
    return orchestrator


def test_recovery_replan_requires_explicit_authorization_receipt():
    orchestrator = _failed_orchestrator()
    actions = [ActionSpec("replacement_write", {"value": 2}, "replacement")]
    receipt = orchestrator.authorize_replan("approval-1", actions)

    assert isinstance(receipt, ReplanAuthorization)
    assert orchestrator.next_phase() == "RECOVERY_REPLAN"

    result = orchestrator.install_authorized_replan(receipt, actions)
    assert result.satisfied is False
    assert orchestrator.next_phase() == "ACTION"


def test_replan_rejects_tampered_actions():
    orchestrator = _failed_orchestrator()
    authorized = [ActionSpec("replacement_write", {"value": 2}, "replacement")]
    receipt = orchestrator.authorize_replan("approval-2", authorized)
    tampered = [ActionSpec("replacement_write", {"value": 999}, "replacement")]

    with pytest.raises(RuntimeError, match="do not match"):
        orchestrator.install_authorized_replan(receipt, tampered)


def test_replan_rejects_fabricated_receipt():
    orchestrator = _failed_orchestrator()
    actions = [ActionSpec("replacement_write", {"value": 2}, "replacement")]
    fabricated = ReplanAuthorization.issue(
        {"ready": False, "revision": 2}, actions, "forged"
    )

    with pytest.raises(RuntimeError, match="does not match"):
        orchestrator.install_authorized_replan(fabricated, actions)


def test_authorization_receipt_is_bound_to_evidence_and_actions():
    actions = [ActionSpec("write", {"value": 1}, "write")]
    receipt = ReplanAuthorization.issue({"ready": False}, actions, "approval-3")

    assert receipt.matches({"ready": False}, actions)
    assert not receipt.matches({"ready": True}, actions)
    assert not receipt.matches({"ready": False}, [ActionSpec("write", {"value": 2}, "write")])
