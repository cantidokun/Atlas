"""Provider-neutral planning runtime.

The runtime owns the stable handoff from a planner provider into Atlas's
validated task-plan proposal type. It intentionally has no knowledge of any
specific model, model SDK, transport, authorization, or execution system.
"""
from __future__ import annotations

from typing import Any, Optional, Set

from planning.planner_provider import PlannerProvider, PlannerProviderError
from planning.task_planner import TaskPlanProposal, TaskPlanValidationError


class PlanningRuntime:
    """Turn provider output into an Atlas planning proposal without authorizing it."""

    def __init__(self, provider: PlannerProvider):
        if not isinstance(provider, PlannerProvider):
            raise TypeError("provider must implement PlannerProvider")
        self.provider = provider

    def build_proposal(
        self,
        model_output: Any,
        *,
        allowed_tools: Optional[Set[str]] = None,
    ) -> Optional[TaskPlanProposal]:
        try:
            proposal = self.provider.build_proposal(
                model_output,
                allowed_tools=allowed_tools,
            )
        except TaskPlanValidationError:
            # Preserve the planning trust-boundary error so callers can
            # distinguish an inadmissible tool/argument from provider failure.
            raise
        except (ValueError, TypeError) as exc:
            raise PlannerProviderError(str(exc)) from exc

        if proposal is not None and not isinstance(proposal, TaskPlanProposal):
            raise PlannerProviderError("planner provider returned an invalid proposal")
        return proposal
