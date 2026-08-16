"""Tests for the structured task-plan proposal boundary."""

import pytest

from action_plan import ActionPlan
from evidence_plan import EvidencePlan
from task_planner import (
    TaskPlanValidationError,
    build_task_plan,
    instantiate_plans,
)

ALLOWED_TOOLS = {"inspect_scene", "inspect_object_relationship", "move_object"}


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
                    "arguments": {
                        "file_name": "scene.blend",
                        "object_name": "Goal_Left_post",
                        "location": [1, 0, 0],
                    },
                    "name": "move",
                }
            ],
        },
        allowed_tools=ALLOWED_TOOLS,
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
            allowed_tools=ALLOWED_TOOLS,
        )


def test_missing_arguments_object_is_rejected():
    with pytest.raises(TaskPlanValidationError, match="arguments"):
        build_task_plan(
            {"evidence": [], "actions": [{"tool": "move_object", "arguments": []}]},
            allowed_tools=ALLOWED_TOOLS,
        )


def test_invalid_top_level_shape_is_rejected():
    with pytest.raises(TaskPlanValidationError, match="object"):
        build_task_plan([], allowed_tools=ALLOWED_TOOLS)


def test_validation_does_not_authorize_or_execute_actions():
    proposal = build_task_plan(
        {
            "evidence": [],
            "actions": [
                {
                    "tool": "move_object",
                    "arguments": {
                        "file_name": "scene.blend",
                        "object_name": "Goal_Left_post",
                        "location": [0, 0, 0],
                    },
                }
            ],
        },
        allowed_tools=ALLOWED_TOOLS,
    )
    _, actions = instantiate_plans(proposal)

    assert actions.current_index == 0
    assert not actions.complete


def test_unknown_argument_is_rejected():
    with pytest.raises(TaskPlanValidationError, match="Unknown argument"):
        build_task_plan(
            {
                "evidence": [],
                "actions": [
                    {
                        "tool": "move_object",
                        "arguments": {
                            "file_name": "scene.blend",
                            "object_name": "Goal_Left_post",
                            "location": [0, 0, 0],
                            "target": [0, 0, 0],
                        },
                    }
                ],
            },
            allowed_tools=ALLOWED_TOOLS,
        )


def test_wrong_tool_argument_shape_is_rejected():
    with pytest.raises(TaskPlanValidationError, match="exactly 3 numbers"):
        build_task_plan(
            {
                "evidence": [],
                "actions": [
                    {
                        "tool": "move_object",
                        "arguments": {
                            "file_name": "scene.blend",
                            "object_name": "Goal_Left_post",
                            "location": [0, 0],
                        },
                    }
                ],
            },
            allowed_tools=ALLOWED_TOOLS,
        )


def test_generic_move_object_accepts_non_goalpost_names():
    proposal = build_task_plan(
        {
            "evidence": [],
            "actions": [
                {
                    "tool": "move_object",
                    "arguments": {
                        "file_name": "scene.blend",
                        "object_name": "TrainingCone_A",
                        "location": [0, 0, 0],
                    },
                }
            ],
        },
        allowed_tools=ALLOWED_TOOLS,
    )
    assert proposal.actions[0].arguments["object_name"] == "TrainingCone_A"


def test_relationship_schema_requires_exact_named_objects():
    with pytest.raises(TaskPlanValidationError, match="Missing argument"):
        build_task_plan(
            {
                "evidence": [
                    {
                        "tool": "inspect_object_relationship",
                        "arguments": {"file_name": "scene.blend", "object1_name": "Goal_Left_post"},
                    }
                ],
                "actions": [],
            },
            allowed_tools=ALLOWED_TOOLS,
        )
