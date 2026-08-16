import pytest

from planning.action_plan import ActionSpec
from planning.future_execution_controller import FutureExecutionController, FutureExecutionError
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def make_generator():
    return DeterministicFutureGenerator(TargetStateEvaluator([StateInvariant("ready", lambda e: e["ready"] is True)]))


def make_actions():
    return [
        ActionSpec("move_object", {"object_name": "A", "location": [1, 2, 3]}, "move A"),
        ActionSpec("move_object", {"object_name": "B", "location": [4, 5, 6]}, "move B"),
    ]


def test_controller_enforces_full_incorrect_future():
    controller = FutureExecutionController.from_target_decision(make_generator(), False, make_actions())
    assert controller.current_step.phase == "EVIDENCE"
    controller.advance_evidence()
    controller.resolve_target(False)
    controller.execute_current_action("move_object", {"object_name": "A", "location": [1, 2, 3]}, {"status": "moved"}, True)
    controller.execute_current_action("move_object", {"object_name": "B", "location": [4, 5, 6]}, {"status": "moved"}, True)
    controller.verify(True)
    controller.complete_future()
    assert controller.verification_satisfied is True
    assert controller.complete is True


def test_controller_rejects_wrong_action():
    controller = FutureExecutionController.from_target_decision(make_generator(), False, make_actions())
    controller.advance_evidence()
    controller.resolve_target(False)
    with pytest.raises(FutureExecutionError):
        controller.execute_current_action("move_object", {"object_name": "B", "location": [4, 5, 6]}, {}, True)
    assert controller.blocked is True


def test_controller_blocks_on_failed_action():
    controller = FutureExecutionController.from_target_decision(make_generator(), False, make_actions())
    controller.advance_evidence()
    controller.resolve_target(False)
    with pytest.raises(FutureExecutionError):
        controller.execute_current_action("move_object", {"object_name": "A", "location": [1, 2, 3]}, {"error": "boom"}, False)
    assert controller.blocked is True


def test_controller_requires_successful_verification():
    controller = FutureExecutionController.from_target_decision(make_generator(), True, make_actions())
    controller.advance_evidence()
    controller.resolve_target(True)
    controller.skip_writes()
    with pytest.raises(FutureExecutionError):
        controller.verify(False)
    assert controller.blocked is True


def test_controller_rejects_target_decision_that_conflicts_with_future():
    controller = FutureExecutionController.from_target_decision(make_generator(), True, make_actions())
    controller.advance_evidence()
    with pytest.raises(FutureExecutionError):
        controller.resolve_target(False)
    assert controller.blocked is True
