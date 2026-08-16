"""Tests for the structured task-plan proposal boundary."""

import pytest

from action_plan import ActionPlan
from evidence_plan import EvidencePlan
from task_planner import (
    TaskPlanValidationError,
    build_task_plan,
    instantiate_plans,
)


def test_builds_inert_evidence_and_action_proposal():
    proposal = build_task_plan(
        {
            "evidence": [
                {
                    "tool": "inspect_scene",
                    "arguments": {"file_name": "scene.blend"},
                    "name": "scene",
                }
            ],
            "actions": [
                {
                    "tool": "move_object",
                    "arguments": {"object_name": "A", "location": [1, 0, 0]},
                    "name": "move",
                }
            ],
        },
        allowed_tools={"inspect_scene", "move_object"},
    )

    evidence, actions = instantiate_plans(proposal)
    assert isinstance(evidence, EvidencePlan)
    assert isinstance(actions, ActionPlan)
    assert evidence.next_request.tool == "inspect_scene"
    assert actions.next_action.tool == "move_object"


def test_unknown_tool_is_rejected_before_plan_creation():
    with pytest.raises(TaskPlanValidationError, match="not allowed"):
        build_task_plan(
            {"evidence": [], "actions": [{"tool": "delete_everything", "arguments": {}}]},
            allowed_tools={"inspect_scene", "move_object"},
        )


def test_missing_arguments_object_is_rejected():
    with pytest.raises(TaskPlanValidationError, match="arguments"):
        build_task_plan(
            {"evidence": [], "actions": [{"tool": "move_object", "arguments": []}]},
            allowed_tools={"move_object"},
        )


def test_invalid_top_level_shape_is_rejected():
    with pytest.raises(TaskPlanValidationError, match="object"):
        build_task_plan([], allowed_tools={"move_object"})


def test_validation_does_not_authorize_or_execute_actions():
    proposal = build_task_plan(
        {
            "evidence": [],
            "actions": [{"tool": "move_object", "arguments": {"object_name": "A"}}],
        },
        allowed_tools={"move_object"},
    )
    _, actions = instantiate_plans(proposal)

    assert actions.current_index == 0
    assert not actions.complete
