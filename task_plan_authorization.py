"""Authorization gate for model-proposed Atlas plans.

This module sits between untrusted Qwen planning output and executable
planning state. A valid structure is not enough to authorize a write.
Authorization is an explicit Python-side decision based on the current task,
evidence state, and allowed tools.
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
) -> bool:
    """Apply explicit Python-side authorization rules to a validated plan.

    Read-only actions may execute with normal tool authorization. Actions
    marked ``requires_write=True`` additionally require explicit write
    authorization. This keeps inspection separate from state-changing work.
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

        if action.requires_write and not allow_writes:
            raise TaskPlanAuthorizationError(
                "Write authorization must be explicitly enabled by Python."
            )

    return True
