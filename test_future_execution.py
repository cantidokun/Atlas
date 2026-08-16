import pytest

from action_plan import ActionSpec
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _future(satisfied=False):
    generator = DeterministicFutureGenerator(
        TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    )
    return generator.generate(satisfied, [ActionSpec("write", {"value": 1}, "write")])


def test_execution_requires_checkpoints_in_order():
    controller = FutureExecutionController(_future(False))
    assert controller.current_step.phase == "EVIDENCE"
    with pytest.raises(RuntimeError, match="not an executable ACTION"):
        controller.execute_current(lambda _tool, _args: {})
    controller.acknowledge({"source": "authoritative"})
    assert controller.current_step.phase == "TARGET"
    controller.acknowledge({"satisfied": False})
    assert controller.current_step.phase == "ACTION"


def test_action_executor_cannot_choose_or_skip_action():
    controller = FutureExecutionController(_future(False))
    controller.acknowledge()
    controller.acknowledge()
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return {"ok": True}

    controller.execute_current(execute)
    assert calls == [("write", {"value": 1})]
    assert controller.current_step.phase == "VERIFICATION"


def test_failed_action_blocks_future():
    controller = FutureExecutionController(_future(False))
    controller.acknowledge()
    controller.acknowledge()
    result = controller.execute_current(lambda _tool, _args: {"error": "nope"})
    assert result["error"] == "nope"
    assert controller.blocked
    assert controller.current_step is None
    with pytest.raises(RuntimeError, match="already resolved"):
        controller.verify({"satisfied": True})


def test_verification_must_pass_before_completion():
    controller = FutureExecutionController(_future(False))
    controller.acknowledge()
    controller.acknowledge()
    controller.execute_current(lambda _tool, _args: {"ok": True})
    controller.verify({"satisfied": True})
    assert controller.current_step.phase == "COMPLETE"
    result = controller.finalize()
    assert result["complete"] is True
    assert controller.complete


def test_failed_verification_blocks_completion():
    controller = FutureExecutionController(_future(False))
    controller.acknowledge()
    controller.acknowledge()
    controller.execute_current(lambda _tool, _args: {"ok": True})
    controller.verify({"satisfied": False})
    assert controller.blocked
    with pytest.raises(RuntimeError, match="blocked"):
        controller.finalize()


def test_already_satisfied_future_contains_no_executable_action():
    controller = FutureExecutionController(_future(True))
    controller.acknowledge()
    controller.acknowledge()
    assert controller.current_step.phase == "SKIP_WRITES"
    assert controller.next_action is None
    controller.acknowledge({"skipped": True})
    assert controller.current_step.phase == "VERIFICATION"
    controller.verify({"satisfied": True})
    controller.finalize()
    assert controller.complete


def test_mutating_authorized_future_blocks_execution():
    controller = FutureExecutionController(_future(False))
    controller.acknowledge()
    controller.acknowledge()

    # Simulate an external/model mutation after the future was authorized.
    controller.steps[2].action["arguments"]["value"] = 999

    with pytest.raises(RuntimeError, match="integrity check failed"):
        controller.execute_current(lambda _tool, _args: {"ok": True})

    assert controller.blocked
    assert controller.failed["exception_type"] == "FuturePlanIntegrityError"
