"""Fail-closed decisioning after a fresh Unreal state reassessment."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_recovery_policy import (
    UnrealRecoveryAssessment,
    UnrealRecoveryDisposition,
)
from planning.unreal_state_verifier import UnrealStateVerificationError, verify_actor_location


class UnrealReassessmentOutcome(str, Enum):
    CONFIRMED = "confirmed"
    STATE_CHANGED = "state_changed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HALT = "halt"


@dataclass(frozen=True)
class UnrealReassessmentDecision:
    outcome: UnrealReassessmentOutcome
    state_uncertain: bool
    reason: str


def decide_reassessment(
    assessment: UnrealRecoveryAssessment,
    evidence: UnrealEvidence,
    expected_location: Mapping[str, float],
) -> UnrealReassessmentDecision:
    """Consume fresh read evidence without authorizing a mutation.

    A matching location resolves the uncertainty. A mismatch or malformed
    observation never authorizes a retry; it instead produces a terminal
    ``STATE_CHANGED``/``INSUFFICIENT_EVIDENCE`` decision for a new planner.
    """
    if not isinstance(assessment, UnrealRecoveryAssessment):
        raise TypeError("assessment must be an UnrealRecoveryAssessment instance")
    if assessment.disposition is not UnrealRecoveryDisposition.REASSESS_STATE:
        raise ValueError("reassessment decision requires REASSESS_STATE assessment")
    if not assessment.requires_fresh_evidence:
        raise ValueError("reassessment decision requires fresh evidence")
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if tuple(evidence.entity_ids) != tuple(assessment.target_entity_ids):
        raise ValueError("fresh evidence targets do not match reassessment targets")

    try:
        verify_actor_location(evidence, expected_location)
    except UnrealStateVerificationError as exc:
        return UnrealReassessmentDecision(
            outcome=UnrealReassessmentOutcome.STATE_CHANGED,
            state_uncertain=False,
            reason=f"Fresh Unreal state does not match the previously requested location: {exc}",
        )
    except (TypeError, ValueError) as exc:
        return UnrealReassessmentDecision(
            outcome=UnrealReassessmentOutcome.INSUFFICIENT_EVIDENCE,
            state_uncertain=True,
            reason=f"Fresh Unreal evidence cannot establish the requested state: {exc}",
        )

    return UnrealReassessmentDecision(
        outcome=UnrealReassessmentOutcome.CONFIRMED,
        state_uncertain=False,
        reason="Fresh Unreal evidence confirms the previously requested actor location.",
    )
