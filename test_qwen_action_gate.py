import pytest

from qwen_action_gate import authorize_qwen_action_plan
from task_plan_authorization import TaskPlanAuthorizationError
from task_planner import build_task_plan


ALLOWED = {"inspect_scene", "move_object"}


def proposal_with_move():
    return build_task_plan(
        {
            "evidence": [{
                "tool": "inspect_scene",
                "arguments": {"file_name": "goalpost_test.blend"},
                "name": "inspect scene",
            }],
            "actions": [{
                "tool": "move_object",
                "arguments": {
                    "file_name": "goalpost_test.blend",
                    "object_name": "Goal_Left_post",
                    "location": [0.0, 5.233, 0.0],
                },
                "name": "move left post",
            }],
        },
        allowed_tools=ALLOWED,
    )


def test_valid_action_proposal_is_still_denied_by_default():
    with pytest.raises(TaskPlanAuthorizationError, match="Write authorization"):
        authorize_qwen_action_plan(
            proposal_with_move(),
            evidence_complete=True,
            allowed_action_tools={"move_object"},
        )


def test_action_is_denied_before_evidence_is_complete():
    with pytest.raises(TaskPlanAuthorizationError, match="before required evidence"):
        authorize_qwen_action_plan(
            proposal_with_move(),
            evidence_complete=False,
            allowed_action_tools={"move_object"},
            allow_writes=True,
        )


def test_action_tool_must_be_python_allowlisted():
    with pytest.raises(TaskPlanAuthorizationError, match="not allowed"):
        authorize_qwen_action_plan(
            proposal_with_move(),
            evidence_complete=True,
            allowed_action_tools={"inspect_scene"},
            allow_writes=True,
        )


def test_explicit_python_write_authorization_allows_proposal_to_enter_execution():
    assert authorize_qwen_action_plan(
        proposal_with_move(),
        evidence_complete=True,
        allowed_action_tools={"move_object"},
        allow_writes=True,
    ) is True
