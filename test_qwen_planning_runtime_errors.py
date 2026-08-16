"""Failure-path tests for Qwen planning runtime."""

import pytest

from qwen_planning_runtime import parse_qwen_plan
from task_planner import TaskPlanValidationError


def test_disallowed_tool_fails_before_execution():
    content = '''ATLAS_TASK_PLAN: {
      "evidence": [],
      "actions": [{"tool": "delete_object", "arguments": {"object_name": "A"}}]
    }'''

    with pytest.raises(TaskPlanValidationError, match="not allowed"):
        parse_qwen_plan(content, allowed_tools={"move_object"})


def test_malformed_json_returns_none():
    content = "ATLAS_TASK_PLAN: {not valid json"
    assert parse_qwen_plan(content) is None
