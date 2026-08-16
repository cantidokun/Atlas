import pytest

from action_plan import ActionSpec
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.future_recovery import FutureRecoveryGate, RecoveryDisposition
from planning.target_state import StateInvariant, TargetStateEvaluator


def _evaluator():
    return TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])


def _failed_action_controller():
    actions = [ActionSpec("write", {"value": 1}, "write")]
    steps = DeterministicFutureGenerator(_evaluator()).generate(False, actions)
    controller = FutureExecutionController(steps)
    controller.acknowledge({"evidence": True})
    controller.acknowledge({"satisfied": False})
    controller.execute_current(lambda _tool, _args: (_ for _ in ()).throw(RuntimeError("write failed")))
    return controller


def test_action_failure_requires_fresh_evidence_before_recovery():
    gate = FutureRecoveryGate(_failed_action_controller())
    decision = gate.classify_failure()
    assert decision.disposition is RecoveryDisposition.REACQUIRE_EVIDENCE
    assert gate.blocked
    with pytest.raises(RuntimeError):
        gate.authorize_retry()


def test_replan_cannot_be_authorized_without_fresh_evidence():
    actions = [ActionSpec("write", {}, "write")]
    steps = DeterministicFutureGenerator(_evaluator()).generate(False, actions)
    controller = FutureExecutionController(steps)
    controller.acknowledge({"evidence": True})
    controller.acknowledge({"satisfied": False})
    controller.execute_current(lambda _tool, _args: {"error": "rejected"})
    gate = FutureRecoveryGate(controller)
    assert gate.classify_failure().disposition is RecoveryDisposition.REACQUIRE_EVIDENCE
    with pytest.raises(RuntimeError):
        gate.authorize_replan()


def test_verification_failure_requires_replan_after_fresh_evidence():
    actions = [ActionSpec("write", {}, "write")]
    steps = DeterministicFutureGenerator(_evaluator()).generate(False, actions)
    controller = FutureExecutionController(steps)
    controller.acknowledge({"evidence": True})
    controller.acknowledge({"satisfied": False})
    controller.execute_current(lambda _tool, _args: {"ok": True})
    controller.verify({"satisfied": False})

    gate = FutureRecoveryGate(controller)
    decision = gate.classify_failure()
    assert decision.disposition is RecoveryDisposition.REPLAN_REQUIRED
    gate.record_fresh_evidence({"ready": False, "fresh": True})
    assert gate.authorize_replan()["fresh"] is True


def test_non_action_failure_defaults_to_abort():
    actions = [ActionSpec("write", {}, "write")]
    steps = DeterministicFutureGenerator(_evaluator()).generate(False, actions)
    controller = FutureExecutionController(steps)
    controller.failed = {"phase": "EVIDENCE", "error": "bad evidence"}
    gate = FutureRecoveryGate(controller)
    assert gate.classify_failure().disposition is RecoveryDisposition.ABORT
