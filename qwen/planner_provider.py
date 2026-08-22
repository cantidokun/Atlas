"""Qwen implementation of the generic Atlas planner-provider boundary."""
from __future__ import annotations

from typing import Optional, Set

from planning.planner_provider import PlannerProvider
from planning.task_planner import TaskPlanProposal
from qwen.planning_bridge import build_proposal_from_qwen


class QwenPlannerProvider(PlannerProvider):
    """Adapt structured Qwen output without exposing Qwen to Atlas execution."""

    def build_proposal(
        self,
        model_output: str,
        *,
        allowed_tools: Optional[Set[str]] = None,
    ) -> Optional[TaskPlanProposal]:
        if not isinstance(model_output, str):
            return None
        return build_proposal_from_qwen(model_output, allowed_tools=allowed_tools)
