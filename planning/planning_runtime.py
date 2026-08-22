"""Provider-neutral planning runtime.

The runtime owns the stable handoff from a planner provider into Atlas's
validated task-plan proposal type. It intentionally has no knowledge of any
specific model, model SDK, transport, authorization, or execution system.
"""
from __future__ import annotations

from typing import Any, Optional, Set

from planning.planner_provider import PlannerProvider, PlannerProviderError
from planning.planning_orchestrator import PlanningOrchestrator
from planning.task_planner import (
    TaskPlanProposal,
    TaskPlanValidationError,
    instantiate_authorized_plans,
)


class PlanningRuntime:
    """Turn provider output into validated plans at an explicit trust boundary."""

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

    def build_authorized_plans(
        self,
        model_output: Any,
        *,
        authorization_id: str,
        allowed_tools: Optional[Set[str]] = None,
    ):
        """Build, validate, and explicitly authorize one exact action plan.

        Provider output is validated before authorization is even considered.
        The returned action plan therefore carries a receipt bound to the
        exact action sequence produced by the provider.
        """
        proposal = self.build_proposal(model_output, allowed_tools=allowed_tools)
        if proposal is None:
            return None
        return instantiate_authorized_plans(
            proposal,
            authorization_id=authorization_id,
        )

    def build_authorized_orchestrator(
        self,
        model_output: Any,
        *,
        authorization_id: str,
        allowed_tools: Optional[Set[str]] = None,
    ) -> Optional[PlanningOrchestrator]:
        """Build a provider-neutral orchestrator with an authorized action plan.

        This is the final handoff before execution: provider output is parsed
        and validated, the exact action sequence receives one authorization
        receipt, and the resulting plans are placed into the deterministic
        orchestrator. No tool is executed by this method.
        """
        plans = self.build_authorized_plans(
            model_output,
            authorization_id=authorization_id,
            allowed_tools=allowed_tools,
        )
        if plans is None:
            return None
        evidence_plan, action_plan = plans
        return PlanningOrchestrator(evidence_plan, action_plan)
