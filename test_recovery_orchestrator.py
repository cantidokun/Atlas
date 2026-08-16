import pytest

from action_plan import ActionSpec
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.conditional_action_plan import ConditionalActionPlan
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _orchestrator():
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    return ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan([EvidenceRequest("inspect", {}, "inspect")]),
        conditional_plan=ConditionalActionPlan([ActionSpec("write", {"value": 1}, "write")]),
        target_evaluator=evaluator,
    )


def test_action_failure_enters_recovery_and_replan_requires_fresh_evidence():
    orchestrator = _orchestrator()
    orchestrator.acquire_next_evidence(lambda _tool, _args: {"ready": False})
    orchestrator.evaluate_target_state({"ready": False})
    with pytest.raises(RuntimeError, match="write failed"):
        orchestrator.execute_next_action(lambda _tool, _args: (_ for _ in ()).throw(RuntimeError("write failed")))

    assert orchestrator.recovery_gate is not None
    assert orchestrator.next_phase() == "BLOCKED"
    with pytest.raises(RuntimeError):
        orchestrator.authorize_replan("before-evidence", [ActionSpec("write", {"value": 1}, "write")])

    orchestrator.record_recovery_evidence({"ready": False, "fresh": True})
    assert orchestrator.next_phase() == "RECOVERY_REPLAN"
    actions = [ActionSpec("write", {"value": 2}, "write-replanned")]
    authorization = orchestrator.authorize_replan("recovery-test", actions)
    assert authorization.authorization_id == "recovery-test"
    assert orchestrator.recovery_gate.authorize_replan()["fresh"] is True


def test_authorized_replan_replaces_failed_future():
    orchestrator = _orchestrator()
    orchestrator.acquire_next_evidence(lambda _tool, _args: {"ready": False})
    orchestrator.evaluate_target_state({"ready": False})
    with pytest.raises(RuntimeError):
        orchestrator.execute_next_action(lambda _tool, _args: (_ for _ in ()).throw(RuntimeError("boom")))
    orchestrator.record_recovery_evidence({"ready": False, "fresh": True})

    actions = [ActionSpec("write", {"value": 2}, "write-replanned")]
    authorization = orchestrator.authorize_replan("recovery-test", actions)
    orchestrator.install_authorized_replan(authorization, actions)

    assert orchestrator.next_phase() == "ACTION"
    assert orchestrator.conditional_plan.next_action.name == "write-replanned"
    result = orchestrator.execute_next_action(lambda _tool, _args: {"ok": True})
    assert result["ok"] is True
