"""Authorization gate for model-proposed Atlas plans."""
from typing import Optional, Set
from task_planner import TaskPlanProposal

class TaskPlanAuthorizationError(ValueError):
    """Raised when a proposed plan cannot be authorized for execution."""

def authorize_task_plan(proposal: TaskPlanProposal, *, evidence_complete: bool = False, allowed_action_tools: Optional[Set[str]] = None, allow_writes: bool = False) -> bool:
    if not evidence_complete and proposal.actions:
        raise TaskPlanAuthorizationError("Action plan cannot be authorized before required evidence is complete.")
    for action in proposal.actions:
        if allowed_action_tools is not None and action.tool not in allowed_action_tools:
            raise TaskPlanAuthorizationError(f"Action tool is not allowed: {action.tool}")
        if not allow_writes:
            raise TaskPlanAuthorizationError("Write authorization must be explicitly enabled by Python.")
    return True
