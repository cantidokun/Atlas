"""High-level, receipt-bound Unreal recovery workflow."""

from typing import Optional

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_evidence_digest import digest_evidence_ledger
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_recovery_execution import resume_replacement
from planning.unreal_recovery_sequence import (
    UnrealRecoverySequenceResult,
    assess_reassessment_sequence,
    build_reassessment_plan,
    build_replacement_plan,
)
from planning.unreal_task_planner import UnrealTaskPlan


def build_recovery_receipt(
    reassessment_result: UnrealPlanExecutionResult,
    replacement_plan: UnrealTaskPlan,
    replacement_authorization: UnrealPlanAuthorization,
) -> RecoveryReceipt:
    """Construct the immutable receipt from the actual recovery artifacts.

    The evidence digest is derived from the reassessment ledger. The plan and
    authorization identities are both derived from the exact replacement
    authorization, preventing a caller from supplying an unrelated identity.
    """
    if not isinstance(reassessment_result, UnrealPlanExecutionResult):
        raise TypeError("reassessment_result must be a UnrealPlanExecutionResult instance")
    if not isinstance(replacement_plan, UnrealTaskPlan):
        raise TypeError("replacement_plan must be a UnrealTaskPlan instance")
    if not isinstance(replacement_authorization, UnrealPlanAuthorization):
        raise TypeError("replacement_authorization must be a UnrealPlanAuthorization instance")
    if not reassessment_result.success:
        raise ValueError("cannot issue a recovery receipt from unsuccessful reassessment")
    if not replacement_authorization.matches(replacement_plan):
        raise ValueError("replacement authorization does not match the exact replacement plan")

    evidence_digest = digest_evidence_ledger(reassessment_result.evidence_ledger)
    return RecoveryReceipt(
        evidence_digest,
        replacement_authorization.plan_digest,
        replacement_authorization.authorization_digest,
    )


def execute_receipt_bound_recovery_sequence(
    executor: UnrealPlanExecutor,
    plan: UnrealTaskPlan,
    failure: UnrealPlanExecutionFailure,
    reassessment_authorization: UnrealPlanAuthorization,
    replacement_authorization: Optional[UnrealPlanAuthorization],
    recovery_receipt: RecoveryReceipt,
    *,
    evidence_digest: str,
    authorization_digest: str,
) -> UnrealRecoverySequenceResult:
    """Run reassessment and, if necessary, the receipt-bound replacement.

    Reassessment is always authorized against its exact read-only plan. A
    replacement is never executed merely because the assessment says it is
    needed: the exact replacement plan must additionally match the separate
    Unreal authorization and the immutable recovery receipt.

    The supplied evidence identity must match the canonical digest of the
    freshly reassessed evidence ledger. Authorization identity is independently
    checked against the exact replacement authorization before execution.
    """
    if not isinstance(executor, UnrealPlanExecutor):
        raise TypeError("executor must be a UnrealPlanExecutor instance")
    if not isinstance(plan, UnrealTaskPlan):
        raise TypeError("plan must be a UnrealTaskPlan instance")
    if not isinstance(failure, UnrealPlanExecutionFailure):
        raise TypeError("failure must be a UnrealPlanExecutionFailure instance")
    if not isinstance(reassessment_authorization, UnrealPlanAuthorization):
        raise TypeError("reassessment_authorization must be a UnrealPlanAuthorization instance")
    if replacement_authorization is not None and not isinstance(replacement_authorization, UnrealPlanAuthorization):
        raise TypeError("replacement_authorization must be a UnrealPlanAuthorization instance or None")
    if not isinstance(recovery_receipt, RecoveryReceipt):
        raise TypeError("recovery_receipt must be a RecoveryReceipt instance")

    reassessment_plan = build_reassessment_plan(plan, failure)
    reassessment_result = executor.execute_authorized(
        reassessment_plan,
        reassessment_authorization,
    )

    fresh_evidence_digest = digest_evidence_ledger(reassessment_result.evidence_ledger)
    if evidence_digest != fresh_evidence_digest:
        raise RuntimeError("recovery receipt evidence identity does not match fresh reassessment evidence")

    assessment = assess_reassessment_sequence(
        plan,
        failure,
        reassessment_result,
    )

    if assessment.disposition == "manual_review":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization must not be supplied for manual review")
        return UnrealRecoverySequenceResult(reassessment_result, assessment)

    if assessment.disposition == "already_applied":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization must not be supplied when recovery is already applied")
        return UnrealRecoverySequenceResult(reassessment_result, assessment)

    replacement_plan = build_replacement_plan(plan, assessment)
    if replacement_authorization is None:
        raise ValueError("replacement_required recovery requires a separate replacement authorization")

    expected_authorization_digest = replacement_authorization.authorization_digest
    if authorization_digest != expected_authorization_digest:
        raise RuntimeError("recovery authorization identity does not match the exact replacement authorization")

    replacement_result = resume_replacement(
        executor,
        replacement_plan,
        replacement_authorization,
        recovery_receipt,
        evidence_digest=evidence_digest,
        authorization_digest=expected_authorization_digest,
    )
    return UnrealRecoverySequenceResult(
        reassessment_result,
        assessment,
        replacement_plan,
        replacement_result,
    )
