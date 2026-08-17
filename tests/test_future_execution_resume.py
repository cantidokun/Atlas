import pytest

from action_plan import ActionSpec
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _future():
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    return DeterministicFutureGenerator(evaluator).generate(
        False,
        [ActionSpec("write", {"value": 1}, "write")],
    )


def _at_action_checkpoint():
    controller = FutureExecutionController(_future())
    controller.acknowledge({"evidence": True})
    controller.acknowledge({"ready": False})
    return controller


def test_resume_requires_exact_plan_digest_and_prefix():
    controller = _at_action_checkpoint()
    snapshot = controller.snapshot()
    resumed = FutureExecutionController.resume_from_snapshot(_future(), snapshot)

    assert resumed.plan_digest == controller.plan_digest
    assert resumed.current_index == controller.current_index
    assert resumed.next_action == controller.next_action


def test_resume_rejects_different_action_plan():
    controller = _at_action_checkpoint()
    snapshot = controller.snapshot()
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    different = DeterministicFutureGenerator(evaluator).generate(
        False,
        [ActionSpec("write", {"value": 999}, "write")],
    )

    with pytest.raises(RuntimeError, match="does not match"):
        FutureExecutionController.resume_from_snapshot(different, snapshot)


def test_resume_rejects_tampered_history():
    controller = _at_action_checkpoint()
    snapshot = controller.snapshot()
    snapshot["history"][0]["step_id"] = "forged"

    with pytest.raises(RuntimeError, match="history"):
        FutureExecutionController.resume_from_snapshot(_future(), snapshot)


def test_resumed_future_can_continue_without_reauthoring_or_reordering():
    controller = _at_action_checkpoint()
    resumed = FutureExecutionController.resume_from_snapshot(_future(), controller.snapshot())

    result = resumed.execute_current(lambda tool, args: {"tool": tool, "args": args, "ok": True})
    assert result["ok"] is True
    assert resumed.current_step.phase == "VERIFICATION"
