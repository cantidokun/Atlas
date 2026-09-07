"""Pure routing decision for the M11 router.

Deterministically picks the lowest-capable validated model profile for a task's
final tier. Never consults model self-report; never reaches production authority.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §5, §6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from planning.m11_router.model_profile import ModelProfile, ModelTier, tier_index
from planning.m11_router.risk import RiskAssessment


class NoCapableProfileError(ValueError):
    """Raised (fail-closed) when no validated profile can satisfy the task."""


# Friendly alias used by callers that prefer a router-scoped name.
RouterCapableProfileError = NoCapableProfileError


@dataclass(frozen=True)
class ModelSelection:
    """Immutable selection of a tier + model profile for one task."""

    task_id: str
    task_classes: frozenset = field(default_factory=frozenset)
    required_tier: ModelTier = ModelTier.L0
    profile: Optional[ModelProfile] = None
    reasons: tuple[str, ...] = ()
    risk: Optional[RiskAssessment] = None

    @property
    def selected_model_id(self) -> Optional[str]:
        return self.profile.model_id if self.profile is not None else None

    @property
    def selected_tier(self) -> ModelTier:
        return self.profile.tier if self.profile is not None else self.required_tier


@dataclass(frozen=True)
class RouterDecision:
    """The router's pure decision output for a task (immutable)."""

    task_id: str
    risk: RiskAssessment
    selection: Optional[ModelSelection] = None
    needs_human_review: bool = False
    failure_reason: Optional[str] = None


def select_profile(
    task_id: str,
    risk: RiskAssessment,
    profiles: Sequence[ModelProfile],
    *,
    require_task_class_support: bool = True,
) -> ModelSelection:
    """Pick the cheapest (lowest-tier) validated profile that can handle the task.

    ``required_tier`` = risk.final_tier. A profile matches only if:
      - its ``capability_floor >= required_tier`` (design §6 step 4), and
      - (optionally) it supports at least one of the task's classes.
    Returns the LOWEST-tier matching profile, deterministic (stable sort by tier
    index then model_id). Raises ``NoCapableProfileError`` when none matches
    (fail-closed -> caller routes to NEEDS_HUMAN_REVIEW).
    """
    if risk is None:
        raise ValueError("risk assessment is required")
    candidates: List[ModelProfile] = []
    for p in profiles:
        if tier_index(p.capability_floor) < tier_index(risk.final_tier):
            continue
        if require_task_class_support and not (set(risk.task_classes) & set(p.supported_task_classes)):
            continue
        candidates.append(p)
    if not candidates:
        raise NoCapableProfileError(
            f"no validated profile supports tier {risk.final_tier.value} "
            f"for task classes {sorted(risk.task_classes)}"
        )
    # Cheapest-capable: lowest tier index, ties broken by model id for determinism.
    candidates.sort(key=lambda p: (tier_index(p.tier), p.model_id))
    chosen = candidates[0]
    reasons = tuple(risk.reasons) + (
        f"profile={chosen.model_id} (tier {chosen.tier.value})",
    )
    return ModelSelection(
        task_id=task_id,
        task_classes=risk.task_classes,
        required_tier=risk.final_tier,
        profile=chosen,
        reasons=reasons,
        risk=risk,
    )