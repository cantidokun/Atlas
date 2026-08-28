"""Validated handoff from Unreal production planning into execution.

The production composer creates an immutable phase-aware production plan. This
module provides the explicit trust-boundary handoff: validate the concrete plan
and issue its authorization receipt, without executing anything.
"""

from dataclasses import dataclass

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_operation import UnrealProductionPlan


@dataclass(frozen=True)
class UnrealAuthorizedProductionPlan:
    """Exact production plan paired with its immutable authorization receipt."""

    production: UnrealProductionPlan
    authorization: UnrealPlanAuthorization


def authorize_production_plan(
    production: UnrealProductionPlan,
    authorization_id: str,
) -> UnrealAuthorizedProductionPlan:
    """Validate the production object and authorize that exact concrete plan."""
    if not isinstance(production, UnrealProductionPlan):
        raise TypeError("production must be an UnrealProductionPlan instance")
    authorization = UnrealPlanAuthorization.issue(production.plan, authorization_id)
    if not authorization.matches(production.plan):
        raise ValueError("production authorization does not match the exact production plan")
    return UnrealAuthorizedProductionPlan(production=production, authorization=authorization)
