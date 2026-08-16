"""Authorization gate for model-proposed Atlas plans.

This module sits between untrusted Qwen planning output and executable
planning state. A valid structure is not enough to authorize a write.
Authorization is an explicit Python-side decision based on the current task,
evidence state, and trusted tool capabilities.
"""

from typing import Optional, Set

from task_planner import TaskPlanProposal
from tools.dispatcher import WRITE_TOOLS


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

    Trusted capability metadata comes from the Python tool registry, not from
    model-provided ``requires_write`` flags. A caller may provide a narrower
    ``write_action_tools`` set for a specific execution context, but omitting it
    no longer makes a real write tool implicitly read-only.
    """
    if not evidence_complete and proposal.actions:
        raise TaskPlanAuthorizationError(
            "Action plan cannot be authorized before required evidence is complete."
        )

    trusted_write_tools = (
        WRITE_TOOLS if write_action_tools is None else write_action_tools
    )

    for action in proposal.actions:
        if allowed_action_tools is not None and action.tool not in allowed_action_tools:
            raise TaskPlanAuthorizationError(
                f"Action tool is not allowed: {action.tool}"
            )

        requires_write = action.tool in trusted_write_tools
        if requires_write and not allow_writes:
            raise TaskPlanAuthorizationError(
                "Write authorization must be explicitly enabled by Python."
            )

    return True
