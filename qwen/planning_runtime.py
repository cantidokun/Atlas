"""Read-only runtime adapter for structured Qwen task-plan proposals."""
from typing import Optional, Set
from qwen_planning_bridge import build_proposal_from_qwen
from task_planner import TaskPlanProposal

def parse_qwen_plan(content: str, allowed_tools: Optional[Set[str]] = None) -> Optional[TaskPlanProposal]:
    return build_proposal_from_qwen(content, allowed_tools=allowed_tools)

def planning_summary(proposal: TaskPlanProposal) -> dict:
    return {"evidence_count": len(proposal.evidence), "action_count": len(proposal.actions), "evidence_tools": [request.tool for request in proposal.evidence], "action_tools": [action.tool for action in proposal.actions], "execution_authorized": False}
