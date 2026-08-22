"""Compatibility runtime for the Qwen planner provider."""
from __future__ import annotations

from typing import Optional, Set

from planning.planning_runtime import PlanningRuntime
from planning.task_planner import TaskPlanProposal
from qwen.planner_provider import QwenPlannerProvider

_PROVIDER = QwenPlannerProvider()
_RUNTIME = PlanningRuntime(_PROVIDER)


def parse_qwen_plan(
    content: str,
    allowed_tools: Optional[Set[str]] = None,
) -> Optional[TaskPlanProposal]:
    """Preserve the existing Qwen API while routing through the generic runtime."""
    return _RUNTIME.build_proposal(content, allowed_tools=allowed_tools)


def planning_summary(proposal: TaskPlanProposal) -> dict:
    return {
        "evidence_count": len(proposal.evidence),
        "action_count": len(proposal.actions),
        "evidence_tools": [request.tool for request in proposal.evidence],
        "action_tools": [action.tool for action in proposal.actions],
        "execution_authorized": False,
    }
