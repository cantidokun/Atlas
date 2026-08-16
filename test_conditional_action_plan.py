import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan


ACTIONS = [
    ActionSpec(
        tool="move_object",
        arguments={
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "location": [0, 0, 0],
        },
        name="move",
    )
]


def test_satisfied_target_skips_all_writes():
    plan = ConditionalActionPlan(ACTIONS)
    plan.evaluate(True)

    assert plan.skipped is True
    assert plan.ready_to_execute is False
    assert plan.complete is True
    assert plan.next_action is None
    assert plan.action_plan.completed == []


def test_unsatisfied_target_exposes_authorized_action_sequence():
    plan = ConditionalActionPlan(ACTIONS)
    plan.evaluate(False)

    assert plan.skipped is False
    assert plan.ready_to_execute is True
    assert plan.complete is False
    assert plan.next_action == ACTIONS[0]


def test_execution_requires_evaluation():
    plan = ConditionalActionPlan(ACTIONS)

    with pytest.raises(RuntimeError, match="ready for execution"):
        plan.record_result({"status": "moved"}, success=True)


def test_evaluation_can_only_happen_once():
    plan = ConditionalActionPlan(ACTIONS)
    plan.evaluate(False)

    with pytest.raises(RuntimeError, match="already been evaluated"):
        plan.evaluate(True)


def test_unsatisfied_action_failure_blocks_plan():
    plan = ConditionalActionPlan(ACTIONS)
    plan.evaluate(False)
    plan.record_result({"status": "error"}, success=False)

    assert plan.action_plan.blocked is True
    assert plan.ready_to_execute is False
    assert plan.complete is False
