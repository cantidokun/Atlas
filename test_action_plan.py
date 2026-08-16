"""Tests for the generic Atlas action-plan primitives."""

import pytest

from action_plan import ActionPlan, ActionSpec


def _plan():
    return ActionPlan(
        actions=[
            ActionSpec("move_object", {"object_name": "A", "location": [1, 0, 0]}, "move A"),
            ActionSpec("move_object", {"object_name": "B", "location": [-1, 0, 0]}, "move B"),
            ActionSpec("inspect_object_relationship", {"object1_name": "A", "object2_name": "B"}, "verify"),
        ]
    )


def test_plan_starts_with_first_action():
    plan = _plan()
    assert plan.next_action.name == "move A"
    assert not plan.complete


def test_success_advances_to_next_action():
    plan = _plan()
    plan.record_result({"status": "moved"}, True)
    assert plan.current_index == 1
    assert plan.next_action.name == "move B"


def test_failure_blocks_plan_and_does_not_advance():
    plan = _plan()
    plan.record_result({"error": "write failed"}, False)
    assert plan.current_index == 0
    assert plan.blocked
    assert plan.next_action is None


def test_plan_completes_only_after_all_actions_succeed():
    plan = _plan()
    for result in (
        {"status": "moved"},
        {"status": "moved"},
        {"midpoint": [0.0, 0.0, 0.0]},
    ):
        plan.record_result(result, True)

    assert plan.complete
    assert plan.next_action is None
    assert plan.snapshot()["current_index"] == 3


def test_completed_plan_cannot_be_advanced():
    plan = _plan()
    for _ in plan.actions:
        plan.record_result({}, True)

    with pytest.raises(RuntimeError, match="already complete"):
        plan.record_result({}, True)


def test_blocked_plan_cannot_be_advanced():
    plan = _plan()
    plan.record_result({"error": "failed"}, False)

    with pytest.raises(RuntimeError, match="blocked"):
        plan.record_result({}, True)
