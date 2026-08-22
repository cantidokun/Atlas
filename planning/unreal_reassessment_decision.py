"""Fail-closed decisioning after a fresh Unreal state reassessment."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

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
    """Result of reassessment; it is informational and never authorizes mutation.

    Retry authorization intentionally does not exist as mutable decision data.
    Callers must obtain mutation authorization from the normal planning and
    authorization boundaries after reassessment; a reassessment result alone
    can never authorize a retry.
    """

    outcome: UnrealReassessmentOutcome
    state_uncertain: bool
    reason: str

    @property
    def retry_authorized(self) -> bool:
        """Whether this reassessment result authorizes repeating a mutation.

        Always false by construction. This explicit capability boundary avoids
        treating a state-change or evidence result as implicit retry permission.
        """
        return False

    @property
    def mutation_authorized(self) -> bool:
        """Whether this reassessment result authorizes any mutation."""
        return False


def _validate_fresh_location_evidence(evidence: UnrealEvidence) -> None:
    """Reject malformed observations before semantic mismatch evaluation.

    A malformed observation cannot establish that the actor changed state.
    Keeping this validation separate from ``verify_actor_location`` prevents
    structural evidence errors from being misclassified as state changes.
    """
    for entity_id in evidence.entity_ids:
        entity_state = evidence.observed_state.get(entity_id)
        if not isinstance(entity_state, Mapping):
            raise TypeError(f"fresh evidence for entity '{entity_id}' is not a mapping")
        location = entity_state.get("location")
        if not isinstance(location, Mapping):
            raise TypeError(f"fresh evidence for entity '{entity_id}' is missing location")
        for axis in ("x", "y", "z"):
            value = location.get(axis)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"fresh evidence for entity '{entity_id}' has non-numeric {axis}"
                )


def decide_reassessment(
    assessment: UnrealRecoveryAssessment,
    evidence: UnrealEvidence,
    expected_location: Mapping[str, float],
) -> UnrealReassessmentDecision:
    """Consume fresh read evidence without authorizing a mutation.

    A matching location resolves the uncertainty. A valid but different
    observation produces ``STATE_CHANGED``. Malformed observations remain
    ``INSUFFICIENT_EVIDENCE`` and never establish mutation state.
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
        _validate_fresh_location_evidence(evidence)
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
