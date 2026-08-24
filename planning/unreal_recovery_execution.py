"""Receipt-bound execution boundary for Unreal recovery replacements."""

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan


class UnrealRecoveryExecutionError(RuntimeError):
    """Raised when a recovery receipt cannot authorize replacement execution."""


def resume_replacement(
    executor: UnrealPlanExecutor,
    replacement_plan: UnrealTaskPlan,
    replacement_authorization: UnrealPlanAuthorization,
    recovery_receipt: RecoveryReceipt,
    *,
    evidence_digest: str,
    authorization_digest: str,
) -> UnrealPlanExecutionResult:
    """Execute a recovery replacement only when both authorization layers match.

    The Unreal plan authorization proves that the exact replacement plan was
    approved. The recovery receipt independently proves that the replacement
    is tied to the exact fresh evidence and authorization identity produced by
    the recovery workflow. Neither layer is allowed to substitute for the
    other.
    """
    if not isinstance(executor, UnrealPlanExecutor):
        raise TypeError("executor must be a UnrealPlanExecutor instance")
    if not isinstance(replacement_plan, UnrealTaskPlan):
        raise TypeError("replacement_plan must be a UnrealTaskPlan instance")
    if not isinstance(replacement_authorization, UnrealPlanAuthorization):
        raise TypeError("replacement_authorization must be a UnrealPlanAuthorization instance")
    if not isinstance(recovery_receipt, RecoveryReceipt):
        raise TypeError("recovery_receipt must be a RecoveryReceipt instance")

    if not replacement_authorization.matches(replacement_plan):
        raise UnrealRecoveryExecutionError(
            "replacement authorization does not match the exact replacement plan"
        )

    if not recovery_receipt.matches(
        evidence_digest,
        replacement_authorization.plan_digest,
        authorization_digest,
    ):
        raise UnrealRecoveryExecutionError(
            "recovery receipt does not match fresh evidence, replacement plan, and authorization"
        )

    return executor.execute_authorized(replacement_plan, replacement_authorization)
