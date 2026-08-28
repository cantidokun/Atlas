"""Compatibility bridge from production recovery to the existing receipt workflow.

The production recovery planner owns phase-aware reassessment. The existing
receipt-bound recovery workflow remains the final authorization/evidence gate.
This module connects the two without duplicating that security machinery.
"""

from dataclasses import dataclass
from typing import Optional

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_evidence_digest import digest_evidence_ledger
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_production_recovery import (
    UnrealProductionRecoveryAssessment,
    build_production_reassessment_plan,
    assess_production_reassessment,
    build_production_replacement_plan,
)
from planning.unreal_recovery_workflow import build_recovery_receipt, execute_receipt_bound_recovery_sequence


@dataclass(frozen=True)
class UnrealProductionReceiptRecovery:
    """Production-aware reassessment paired with the canonical recovery receipt."""

    reassessment_plan: object
    reassessment_result: UnrealPlanExecutionResult
    assessment: UnrealProductionRecoveryAssessment
    replacement_plan: Optional[object]
    recovery_receipt: Optional[RecoveryReceipt]


def prepare_production_receipt_recovery(
    executor: UnrealPlanExecutor,
    production: UnrealProductionPlan,
    failure: UnrealPlanExecutionFailure,
    reassessment_authorization: UnrealPlanAuthorization,
    replacement_authorization: Optional[UnrealPlanAuthorization] = None,
) -> UnrealProductionReceiptRecovery:
    """Reassess production state and prepare the canonical receipt when needed."""
    if not isinstance(executor, UnrealPlanExecutor):
        raise TypeError("executor must be a UnrealPlanExecutor instance")
    if not isinstance(production, UnrealProductionPlan):
        raise TypeError("production must be a UnrealProductionPlan instance")
    if not isinstance(failure, UnrealPlanExecutionFailure):
        raise TypeError("failure must be a UnrealPlanExecutionFailure instance")
    if not isinstance(reassessment_authorization, UnrealPlanAuthorization):
        raise TypeError("reassessment_authorization must be a UnrealPlanAuthorization instance")

    reassessment_plan = build_production_reassessment_plan(production, failure)
    if not reassessment_authorization.matches(reassessment_plan):
        raise ValueError("reassessment authorization does not match the exact production reassessment plan")
    reassessment_result = executor.execute_authorized(reassessment_plan, reassessment_authorization)
    assessment = assess_production_reassessment(production, failure, reassessment_result)

    if assessment.disposition == "manual_review":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization must not be supplied for manual review")
        return UnrealProductionReceiptRecovery(reassessment_plan, reassessment_result, assessment, None, None)

    if assessment.disposition == "already_applied":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization must not be supplied when recovery is already applied")
        return UnrealProductionReceiptRecovery(reassessment_plan, reassessment_result, assessment, None, None)

    replacement_plan = build_production_replacement_plan(production, assessment)
    if replacement_authorization is None:
        raise ValueError("replacement_required recovery requires a separate replacement authorization")
    if not replacement_authorization.matches(replacement_plan):
        raise ValueError("replacement authorization does not match the exact production replacement plan")

    receipt = build_recovery_receipt(
        reassessment_result,
        replacement_plan,
        replacement_authorization,
    )
    return UnrealProductionReceiptRecovery(
        reassessment_plan,
        reassessment_result,
        assessment,
        replacement_plan,
        receipt,
    )


def execute_prepared_production_receipt_recovery(
    executor: UnrealPlanExecutor,
    production: UnrealProductionPlan,
    failure: UnrealPlanExecutionFailure,
    prepared: UnrealProductionReceiptRecovery,
    reassessment_authorization: UnrealPlanAuthorization,
    replacement_authorization: Optional[UnrealPlanAuthorization] = None,
) -> object:
    """Execute through the canonical receipt-bound recovery gate."""
    if not isinstance(prepared, UnrealProductionReceiptRecovery):
        raise TypeError("prepared must be a UnrealProductionReceiptRecovery instance")
    if prepared.recovery_receipt is None:
        if replacement_authorization is not None:
            raise ValueError("replacement authorization is invalid without a recovery receipt")
        return prepared
    if prepared.replacement_plan is None or replacement_authorization is None:
        raise ValueError("receipt-bound production recovery requires replacement plan and authorization")

    fresh_digest = digest_evidence_ledger(prepared.reassessment_result.evidence_ledger)
    authorization_digest = replacement_authorization.authorization_digest
    return execute_receipt_bound_recovery_sequence(
        executor,
        production.plan,
        failure,
        reassessment_authorization,
        replacement_authorization,
        prepared.recovery_receipt,
        evidence_digest=fresh_digest,
        authorization_digest=authorization_digest,
    )
