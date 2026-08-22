"""Fail-closed planning of fresh Unreal state reassessment.

This layer converts a recovery assessment into a read-only plan. It never
creates a mutation, authorization, retry, or rollback operation.
"""

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_recovery_policy import (
    UnrealRecoveryAssessment,
    UnrealRecoveryDisposition,
)
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_capability_registry import UnrealCapabilityRegistry


class UnrealReassessmentPlanner:
    """Build the only safe next step for an assessment requiring fresh state."""

    def __init__(self, capabilities=None) -> None:
        self.capabilities = capabilities or UnrealCapabilityRegistry()

    def plan(self, assessment: UnrealRecoveryAssessment) -> UnrealTaskPlan:
        """Return a read-only inspection plan or fail closed."""
        if not isinstance(assessment, UnrealRecoveryAssessment):
            raise TypeError("assessment must be an UnrealRecoveryAssessment instance")
        if assessment.disposition is not UnrealRecoveryDisposition.REASSESS_STATE:
            raise ValueError("reassessment is only permitted for REASSESS_STATE assessments")
        if not assessment.requires_fresh_evidence:
            raise ValueError("reassessment requires an explicit fresh-evidence requirement")
        targets = tuple(assessment.target_entity_ids)
        if not targets:
            raise ValueError("reassessment requires explicit target entity IDs")
        if any(not isinstance(entity_id, str) or not entity_id.strip() for entity_id in targets):
            raise ValueError("reassessment targets must contain only non-empty strings")

        operation = UnrealOperation(
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            name="inspect_target_actors",
            arguments={"entity_ids": targets},
            entity_ids=targets,
        )
        operation = self.capabilities.validate_operation(operation)
        return UnrealTaskPlan(
            intent_id=f"{assessment.failure_class.value}:reassess",
            operations=(operation,),
        )
