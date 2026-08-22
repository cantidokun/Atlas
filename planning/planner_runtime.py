"""Provider-agnostic runtime for converting model output into Atlas plans."""
from __future__ import annotations

from typing import Any, Optional, Set

from planning.planner_provider import PlannerProvider
from planning.task_planner import TaskPlanProposal


class PlannerRuntime:
    """Keep model/provider selection outside Atlas planning primitives."""

    def __init__(self, provider: PlannerProvider):
        if not isinstance(provider, PlannerProvider):
            raise TypeError("provider must implement PlannerProvider")
        self._provider = provider

    @property
    def provider(self) -> PlannerProvider:
        return self._provider

    def build_proposal(
        self,
        model_output: Any,
        *,
        allowed_tools: Optional[Set[str]] = None,
    ) -> Optional[TaskPlanProposal]:
        """Build an inert proposal; authorization and execution remain downstream."""
        return self._provider.build_proposal(
            model_output,
            allowed_tools=allowed_tools,
        )
