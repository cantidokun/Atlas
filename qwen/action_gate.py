"""Bridge Qwen action proposals into the explicit Python authorization gate."""
from typing import Optional, Set
from task_plan_authorization import TaskPlanAuthorizationError, authorize_task_plan
from task_planner import TaskPlanProposal

def authorize_qwen_action_plan(proposal: TaskPlanProposal, *, evidence_complete: bool, allowed_action_tools: Optional[Set[str]] = None, allow_writes: bool = False) -> bool:
    return authorize_task_plan(proposal, evidence_complete=evidence_complete, allowed_action_tools=allowed_action_tools, allow_writes=allow_writes)

__all__ = ["authorize_qwen_action_plan", "TaskPlanAuthorizationError"]
