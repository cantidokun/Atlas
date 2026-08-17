import pytest

from action_plan import ActionSpec
from task_planner import (
    TaskPlanValidationError,
    build_task_plan,
    instantiate_authorized_plans,
)


def _proposal():
    return {
        "evidence": [],
        "actions": [
            {"tool": "move_object", "arguments": {"name": "Cube", "location": [1, 2, 3]}}
        ],
    }


def test_authorized_instantiation_binds_exact_receipt():
    proposal = build_task_plan(_proposal(), allowed_tools={"move_object"})
    _, action_plan = instantiate_authorized_plans(proposal, authorization_id="auth-1")

    assert action_plan.authorized is True
    assert action_plan.authorization.authorization_id == "auth-1"
    assert action_plan.snapshot()["authorized"] is True


def test_authorized_instantiation_rejects_blank_id():
    proposal = build_task_plan(_proposal(), allowed_tools={"move_object"})

    with pytest.raises(ValueError, match="authorization_id"):
        instantiate_authorized_plans(proposal, authorization_id=" ")


def test_authorization_is_issued_from_validated_action_objects():
    proposal = build_task_plan(_proposal(), allowed_tools={"move_object"})
    _, action_plan = instantiate_authorized_plans(proposal, authorization_id="auth-2")

    assert action_plan.actions == proposal.actions
    assert action_plan.authorization.matches(action_plan.actions)
