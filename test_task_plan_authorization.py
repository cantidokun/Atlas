"""Tests for the Python-side authorization boundary."""

import pytest

from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from task_planner import TaskPlanProposal
from task_plan_authorization import (
    TaskPlanAuthorizationError,
    authorize_task_plan,
)


def _proposal(action_tool="move_object"):
    return TaskPlanProposal(
        evidence=[EvidenceRequest("inspect_scene", {})],
        actions=[ActionSpec(action_tool, {"object_name": "A"})],
    )


def test_writes_are_not_authorized_by_default():
    with pytest.raises(TaskPlanAuthorizationError, match="explicitly enabled"):
        authorize_task_plan(_proposal(), evidence_complete=True, allowed_action_tools={"move_object"})


def test_missing_evidence_blocks_action_authorization():
    with pytest.raises(TaskPlanAuthorizationError, match="evidence"):
        authorize_task_plan(
            _proposal(),
            evidence_complete=False,
            allowed_action_tools={"move_object"},
            allow_writes=True,
        )


def test_disallowed_action_tool_is_rejected():
    with pytest.raises(TaskPlanAuthorizationError, match="not allowed"):
        authorize_task_plan(
            _proposal("delete_object"),
            evidence_complete=True,
            allowed_action_tools={"move_object"},
            allow_writes=True,
        )


def test_authorized_plan_is_still_inert():
    proposal = _proposal()
    assert authorize_task_plan(
        proposal,
        evidence_complete=True,
        allowed_action_tools={"move_object"},
        allow_writes=True,
    ) is True
    assert proposal.actions[0].tool == "move_object"
