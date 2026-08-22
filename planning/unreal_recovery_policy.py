"""Fail-closed recovery classification for Unreal plan execution.

This module deliberately classifies failures without performing recovery. A
mutation may have reached Unreal even when its adapter call reports an error,
so automatic retries are unsafe until the resulting state is independently
re-established.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from planning.unreal_plan_executor import UnrealPlanExecutionFailure


class UnrealRecoveryDisposition(str, Enum):
    """Safe next-step classifications for a failed Unreal execution."""

    REASSESS_STATE = "reassess_state"
    HALT = "halt"


class UnrealFailureClass(str, Enum):
    """Semantic classification of the point where execution stopped."""

    OBSERVATION_FAILURE = "observation_failure"
    MUTATION_FAILURE = "mutation_failure"
    POST_WRITE_VERIFICATION_FAILURE = "post_write_verification_failure"
    VERIFICATION_FAILURE = "verification_failure"
    UNKNOWN_FAILURE = "unknown_failure"


@dataclass(frozen=True)
class UnrealRecoveryAssessment:
    """Immutable, non-executing assessment of a failed plan."""

    failure_class: UnrealFailureClass
    disposition: UnrealRecoveryDisposition
    state_uncertain: bool
    reason: str
    target_entity_ids: Tuple[str, ...] = ()
    requires_fresh_evidence: bool = False


def _recovery_targets(failure: UnrealPlanExecutionFailure) -> Tuple[str, ...]:
    """Extract targets from the failed operation and validate prior evidence."""
    operation_targets = tuple(failure.operation_entity_ids)
    evidence_targets = []
    for evidence in failure.completed_evidence:
        for entity_id in evidence.entity_ids:
            if entity_id not in evidence_targets:
                evidence_targets.append(entity_id)

    if operation_targets:
        if any(
            tuple(dict.fromkeys(evidence.entity_ids)) != operation_targets
            for evidence in failure.completed_evidence
        ):
            raise ValueError("completed evidence contains inconsistent recovery targets")
        return operation_targets

    return tuple(evidence_targets)


def assess_unreal_failure(
    failure: UnrealPlanExecutionFailure,
) -> UnrealRecoveryAssessment:
    """Classify a failure and choose a fail-closed next step.

    No automatic retry or rollback is authorized by this function. In
    particular, a failed write or failed post-write verification is treated as
    state-uncertain because the remote side may have applied the mutation
    before reporting an error or may have diverged from the requested state.

    ``target_entity_ids`` identifies the only entities a subsequent fresh
    observation may inspect. ``requires_fresh_evidence`` is explicit so a
    caller cannot interpret ``REASSESS_STATE`` as permission to retry.
    """
    if not isinstance(failure, UnrealPlanExecutionFailure):
        raise TypeError("failure must be an UnrealPlanExecutionFailure instance")

    operation_name = failure.operation_name
    target_entity_ids = _recovery_targets(failure)
    completed = failure.completed_evidence
    has_completed_write = any(
        evidence.operation_name == "set_actor_location" for evidence in completed
    )

    if operation_name.startswith("inspect_"):
        return UnrealRecoveryAssessment(
            failure_class=UnrealFailureClass.OBSERVATION_FAILURE,
            disposition=UnrealRecoveryDisposition.HALT,
            state_uncertain=False,
            reason="Required observation failed before a trustworthy state assessment was established.",
            target_entity_ids=target_entity_ids,
        )

    if operation_name == "set_actor_location":
        return UnrealRecoveryAssessment(
            failure_class=UnrealFailureClass.MUTATION_FAILURE,
            disposition=UnrealRecoveryDisposition.REASSESS_STATE,
            state_uncertain=True,
            reason="A location mutation may have reached Unreal despite the reported failure; re-establish state before any retry.",
            target_entity_ids=target_entity_ids,
            requires_fresh_evidence=True,
        )

    if operation_name == "verify_target_actor_mapping":
        failure_class = (
            UnrealFailureClass.POST_WRITE_VERIFICATION_FAILURE
            if has_completed_write
            else UnrealFailureClass.VERIFICATION_FAILURE
        )
        return UnrealRecoveryAssessment(
            failure_class=failure_class,
            disposition=UnrealRecoveryDisposition.REASSESS_STATE,
            state_uncertain=has_completed_write,
            reason=(
                "Post-write verification failed; the mutation outcome is not trustworthy until state is re-observed."
                if has_completed_write
                else "Verification failed without a completed mutation in the evidence ledger."
            ),
            target_entity_ids=target_entity_ids,
            requires_fresh_evidence=True,
        )

    return UnrealRecoveryAssessment(
        failure_class=UnrealFailureClass.UNKNOWN_FAILURE,
        disposition=UnrealRecoveryDisposition.HALT,
        state_uncertain=True,
        reason="Failure semantics are not established for this operation; automatic recovery is prohibited.",
        target_entity_ids=target_entity_ids,
    )
