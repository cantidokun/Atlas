import pytest

from action_plan import ActionPlan, ActionSpec
from conditional_action import ConditionalActionError, ConditionalActionPlan, TargetCondition


# Compatibility import is intentionally exercised through the root module.
from planning.conditional_action import ConditionalActionPlan as PlanningConditionalActionPlan


def _plan():
    return ActionPlan(
        actions=[
            ActionSpec(
                "move_object",
                {"object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]},
                "move left post",
            ),
            ActionSpec(
                "move_object",
                {"object_name": "Goal_Right_Post", "location": [0.0, -5.233, 0.0]},
                "move right post",
            ),
        ]
    )


def _condition():
    return TargetCondition(path=("midpoint",), expected=[0.0, 0.0, 0.0])


def test_satisfied_target_skips_all_writes():
    plan = ConditionalActionPlan(_plan(), _condition())

    assert plan.evaluate({"midpoint": [0.0, 0.0, 0.0]}) is True
    assert plan.decision == "SKIP_WRITES"
    assert plan.complete
    assert plan.next_action is None
    assert plan.action_plan.current_index == 0


def test_unsatisfied_target_retains_action_plan():
    plan = ConditionalActionPlan(_plan(), _condition())

    assert plan.evaluate({"midpoint": [0.0, 0.069, 0.0]}) is False
    assert plan.decision == "EXECUTE_ACTIONS"
    assert not plan.complete
    assert plan.next_action.name == "move left post"
    assert plan.action_plan.current_index == 0


def test_cannot_expose_actions_before_target_is_evaluated():
    plan = ConditionalActionPlan(_plan(), _condition())

    assert plan.next_action is None
    assert not plan.complete


def test_missing_authoritative_field_is_rejected():
    plan = ConditionalActionPlan(_plan(), _condition())

    with pytest.raises(ConditionalActionError, match="Evidence field is missing"):
        plan.evaluate({"distance": 10.466})


def test_condition_is_evaluated_only_once():
    plan = ConditionalActionPlan(_plan(), _condition())
    plan.evaluate({"midpoint": [0.0, 0.0, 0.0]})

    with pytest.raises(ConditionalActionError, match="already evaluated"):
        plan.evaluate({"midpoint": [0.0, 0.069, 0.0]})


def test_root_compatibility_import_resolves_same_implementation():
    assert ConditionalActionPlan is PlanningConditionalActionPlan
