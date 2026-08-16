"""Authorization gate for model-proposed Atlas plans.

This module sits between untrusted Qwen planning output and executable
planning state. A valid structure is not enough to authorize a write.
Authorization is an explicit Python-side decision based on the current task,
evidence state, and trusted tool capabilities.
"""

from typing import Optional, Set

from task_planner import TaskPlanProposal


class TaskPlanAuthorizationError(ValueError):
    """Raised when a proposed plan cannot be authorized for execution."""


def authorize_task_plan(
    proposal: TaskPlanProposal,
    *,
    evidence_complete: bool = False,
    allowed_action_tools: Optional[Set[str]] = None,
    allow_writes: bool = False,
    write_action_tools: Optional[Set[str]] = None,
) -> bool:
    """Apply explicit Python-side authorization rules to a validated plan.

    When ``write_action_tools`` is supplied, it is trusted Python metadata and
    takes precedence over model-provided ``requires_write`` flags. This prevents
    a model from relabeling a real write tool as read-only.
    """
    if not evidence_complete and proposal.actions:
        raise TaskPlanAuthorizationError(
            "Action plan cannot be authorized before required evidence is complete."
        )

    for action in proposal.actions:
        if allowed_action_tools is not None and action.tool not in allowed_action_tools:
            raise TaskPlanAuthorizationError(
                f"Action tool is not allowed: {action.tool}"
            )

        requires_write = (
            action.tool in write_action_tools
            if write_action_tools is not None
            else action.requires_write
        )
        if requires_write and not allow_writes:
            raise TaskPlanAuthorizationError(
                "Write authorization must be explicitly enabled by Python."
            )

    return True
