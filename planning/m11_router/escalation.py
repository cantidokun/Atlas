"""Finite escalation state for the M11 router.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §6.1.

- MAX_ESCALATIONS_PER_TASK = 3
- MAX_TIER = L3 (no tier above L3)
- Terminal state: NEEDS_HUMAN_REVIEW (no further automatic escalation)
- Prohibited: unbounded escalation, blind reruns, downgrade, escalation loops.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from planning.m11_router.model_profile import ModelTier, tier_index


MAX_ESCALATIONS_PER_TASK = 3
MAX_TIER = ModelTier.L3

_TIERS = [ModelTier.L0, ModelTier.L1, ModelTier.L2, ModelTier.L3]


def next_tier_of(tier: ModelTier, max_tier: ModelTier = MAX_TIER) -> Optional[ModelTier]:
    """Return the next strictly higher tier, or None if already at/beyond max."""
    idx = tier_index(tier)
    if idx >= tier_index(max_tier):
        return None
    return _TIERS[idx + 1]


class EscalationTerminal(Exception):
    """Raised when the task has reached a terminal NEEDS_HUMAN_REVIEW state."""


class EscalationPolicyError(ValueError):
    """Raised on a prohibited escalation (downgrade / blind rerun / over budget)."""


@dataclass(frozen=True)
class EscalationState:
    """Immutable snapshot of escalation progress for one task.

    Escalation metadata survives across attempt records; it is updated by
    transitioning to a NEW state (never mutated in place).
    """

    task_id: str
    attempt_id: Optional[str] = None
    escalation_id: Optional[str] = None
    current_tier: ModelTier = ModelTier.L0
    next_tier: Optional[ModelTier] = None
    escalation_reason: Optional[str] = None
    evidence_state: str = "none"
    escalation_count: int = 0
    terminal: bool = False
    terminal_outcome: Optional[str] = None

    @property
    def human_review_required(self) -> bool:
        return self.terminal and self.terminal_outcome == "NEEDS_HUMAN_REVIEW"


def _terminal(state: EscalationState, reason: str) -> EscalationState:
    return replace(
        state,
        next_tier=None,
        escalation_reason=reason,
        evidence_state="INSUFFICIENT",
        terminal=True,
        terminal_outcome="NEEDS_HUMAN_REVIEW",
    )


class EscalationController:
    """Applies the finite escalation policy (design §6.1)."""

    def __init__(
        self,
        max_escalations: int = MAX_ESCALATIONS_PER_TASK,
        max_tier: ModelTier = MAX_TIER,
    ) -> None:
        if max_escalations < 1:
            raise EscalationPolicyError("max_escalations must be >= 1")
        self._max_escalations = max_escalations
        self._max_tier = max_tier

    def initial(self, task_id: str, tier: ModelTier, attempt_id: str) -> EscalationState:
        return EscalationState(
            task_id=task_id,
            attempt_id=attempt_id,
            escalation_id=None,
            current_tier=tier,
            next_tier=next_tier_of(tier, self._max_tier),
            escalation_reason=None,
            evidence_state="initial",
            escalation_count=0,
        )

    def escalate(
        self,
        state: EscalationState,
        *,
        evidence_failed: bool = False,
        insufficient_evidence: bool = False,
        l3_failed: bool = False,
        reason: str,
        new_attempt_id: str,
        new_escalation_id: str,
    ) -> EscalationState:
        """Transition to the next tier, enforcing finite budget and no-downgrade.

        Returns a NEW immutable state. Reaching the escalation budget, an L3
        failure, or any state with no higher tier terminates the task in
        NEEDS_HUMAN_REVIEW.
        """
        if state.terminal:
            raise EscalationTerminal(
                f"task {state.task_id} is already terminal ({state.terminal_outcome})"
            )
        new_count = state.escalation_count + 1
        if new_count > self._max_escalations:
            return _terminal(state, f"escalation budget exhausted after {self._max_escalations}")

        # L3 failure: no higher tier exists -> terminal NEEDS_HUMAN_REVIEW.
        if l3_failed:
            return _terminal(state, "L3 attempt failed; no higher tier")
        if insufficient_evidence or evidence_failed:
            if not reason:
                raise EscalationPolicyError("escalation requires a reason")
            if tier_index(state.current_tier) >= tier_index(self._max_tier):
                return _terminal(state, "max tier attempted with insufficient evidence")

        # Compute the next tier. Being already at the max tier with no higher
        # option is not a downgrade: it means no further escalation exists.
        nxt = state.next_tier if state.next_tier is not None else next_tier_of(state.current_tier, self._max_tier)
        if nxt is None:
            return _terminal(state, f"no tier above {state.current_tier.value}")
        if tier_index(nxt) <= tier_index(state.current_tier):
            raise EscalationPolicyError("escalation cannot downgrade or stay at same tier")

        return EscalationState(
            task_id=state.task_id,
            attempt_id=new_attempt_id,
            escalation_id=new_escalation_id,
            current_tier=nxt,
            next_tier=next_tier_of(nxt, self._max_tier),
            escalation_reason=reason,
            evidence_state=("failed" if evidence_failed else "insufficient")
            if (evidence_failed or insufficient_evidence)
            else "requested",
            escalation_count=new_count,
        )

    def insufficient_evidence(
        self, state: EscalationState, *, reason: str, new_attempt_id: str, new_escalation_id: str
    ) -> EscalationState:
        """Escalate on insufficient objective evidence (or terminal at max tier)."""
        return self.escalate(
            state,
            insufficient_evidence=True,
            reason=reason,
            new_attempt_id=new_attempt_id,
            new_escalation_id=new_escalation_id,
        )

    def l3_failure(self, state: EscalationState, *, reason: str, new_attempt_id: str, new_escalation_id: str) -> EscalationState:
        return self.escalate(
            state,
            l3_failed=True,
            reason=reason,
            new_attempt_id=new_attempt_id,
            new_escalation_id=new_escalation_id,
        )