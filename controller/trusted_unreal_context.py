
"""Trusted Unreal execution context for the Atlas agent boundary.

This module carries already-authorized Unreal production state into the
agent/controller boundary. It does not create authorization and it never
trusts model-supplied authorization artifacts.
"""

from dataclasses import dataclass

from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_production_planning_boundary import (
    UnrealAuthorizedProductionPlan,
)
from controller.agent_trusted_context import AgentTrustedContext


@dataclass(frozen=True)
class TrustedUnrealContext:
    """Trusted binding between an authorized production and its agent intent."""

    authorized_production: UnrealAuthorizedProductionPlan
    intent: UnrealTaskIntent
    sequence_asset_path: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.authorized_production,
            UnrealAuthorizedProductionPlan,
        ):
            raise TypeError(
                "authorized_production must be an "
                "UnrealAuthorizedProductionPlan instance"
            )

        if not isinstance(self.intent, UnrealTaskIntent):
            raise TypeError(
                "intent must be an UnrealTaskIntent instance"
            )

        if (
            not isinstance(self.sequence_asset_path, str)
            or not self.sequence_asset_path.strip()
        ):
            raise ValueError(
                "sequence_asset_path must be a non-empty Unreal package path"
            )

        normalized_path = self.sequence_asset_path.strip()

        if not normalized_path.startswith("/"):
            raise ValueError(
                "sequence_asset_path must be a non-empty Unreal package path"
            )

        if (
            self.authorized_production.production.plan.intent_id
            != self.intent.intent_id
        ):
            raise ValueError(
                "authorized production plan intent_id must match "
                "the supplied UnrealTaskIntent"
            )

        object.__setattr__(
            self,
            "sequence_asset_path",
            normalized_path,
        )

    def to_trusted_agent_context(self) -> AgentTrustedContext:
        return AgentTrustedContext.from_values(
            {
                "authorized_production": self.authorized_production,
                "intent": self.intent,
                "sequence_asset_path": self.sequence_asset_path,
            }
        )
