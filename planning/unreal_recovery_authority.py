"""Atlas recovery authority binding for Unreal replacement execution.

The Unreal recovery coordinator produces domain-specific reassessment and
replacement artifacts. This module binds those artifacts to Atlas's generic
RecoveryReceipt so a recovery resume cannot drift from the exact fresh
reassessment, replacement plan, or replacement authorization that produced it.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_task_planner import UnrealTaskPlan


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def evidence_digest(result: UnrealPlanExecutionResult) -> str:
    """Digest the exact reassessment evidence ledger used for recovery."""
    if not isinstance(result, UnrealPlanExecutionResult):
        raise TypeError("result must be a UnrealPlanExecutionResult instance")
    payload = {
        "intent_id": result.intent_id,
        "success": result.success,
        "evidence_ledger": [
            {
                "operation_name": evidence.operation_name,
                "entity_ids": tuple(evidence.entity_ids),
                "observed_state": evidence.observed_state,
                "source": evidence.source,
                "verified": evidence.verified,
            }
            for evidence in result.evidence_ledger
        ],
    }
    return _digest(payload)


def replacement_plan_digest(plan: UnrealTaskPlan) -> str:
    """Return the exact plan digest used by UnrealPlanAuthorization."""
    authorization = UnrealPlanAuthorization.issue(plan, "recovery-plan-digest")
    return authorization.plan_digest


def replacement_authorization_digest(authorization: UnrealPlanAuthorization) -> str:
    """Digest the exact Unreal replacement authorization receipt."""
    if not isinstance(authorization, UnrealPlanAuthorization):
        raise TypeError("authorization must be a UnrealPlanAuthorization instance")
    return _digest(authorization.snapshot())


@dataclass(frozen=True)
class UnrealRecoveryAuthority:
    """Immutable binding between fresh evidence, replacement plan, and authorization."""

    receipt: RecoveryReceipt
    reassessment_result: UnrealPlanExecutionResult
    replacement_plan: UnrealTaskPlan
    replacement_authorization: UnrealPlanAuthorization

    @classmethod
    def issue(
        cls,
        reassessment_result: UnrealPlanExecutionResult,
        replacement_plan: UnrealTaskPlan,
        replacement_authorization: UnrealPlanAuthorization,
    ) -> "UnrealRecoveryAuthority":
        if not isinstance(reassessment_result, UnrealPlanExecutionResult):
            raise TypeError("reassessment_result must be a UnrealPlanExecutionResult instance")
        if not isinstance(replacement_plan, UnrealTaskPlan):
            raise TypeError("replacement_plan must be a UnrealTaskPlan instance")
        if not isinstance(replacement_authorization, UnrealPlanAuthorization):
            raise TypeError("replacement_authorization must be a UnrealPlanAuthorization instance")
        if not replacement_authorization.matches(replacement_plan):
            raise ValueError("replacement authorization does not match the exact replacement plan")

        receipt = RecoveryReceipt(
            evidence_digest(reassessment_result),
            replacement_plan_digest(replacement_plan),
            replacement_authorization_digest(replacement_authorization),
        )
        return cls(receipt, reassessment_result, replacement_plan, replacement_authorization)

    def matches(
        self,
        reassessment_result: UnrealPlanExecutionResult,
        replacement_plan: UnrealTaskPlan,
        replacement_authorization: UnrealPlanAuthorization,
    ) -> bool:
        """Return true only when all three recovery identities match exactly."""
        if not isinstance(reassessment_result, UnrealPlanExecutionResult):
            return False
        if not isinstance(replacement_plan, UnrealTaskPlan):
            return False
        if not isinstance(replacement_authorization, UnrealPlanAuthorization):
            return False
        if not replacement_authorization.matches(replacement_plan):
            return False
        return self.receipt.matches(
            evidence_digest(reassessment_result),
            replacement_plan_digest(replacement_plan),
            replacement_authorization_digest(replacement_authorization),
        )

    def require_match(
        self,
        reassessment_result: UnrealPlanExecutionResult,
        replacement_plan: UnrealTaskPlan,
        replacement_authorization: UnrealPlanAuthorization,
    ) -> None:
        """Fail closed when recovery artifacts drift from the authorized binding."""
        if not self.matches(reassessment_result, replacement_plan, replacement_authorization):
            raise ValueError("Unreal recovery authority identity mismatch")

    def snapshot(self) -> Mapping[str, str]:
        return {
            "receipt_digest": self.receipt.receipt_digest,
            "evidence_digest": self.receipt.evidence_digest,
            "plan_digest": self.receipt.plan_digest,
            "authorization_digest": self.receipt.authorization_digest,
        }
