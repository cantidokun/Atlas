"""Immutable authorization receipts for explicit Unreal task plans.

A receipt binds a concrete UnrealTaskPlan to an Atlas authorization identifier.
The receipt is intentionally separate from planning and execution: planning
proposes a plan, authorization approves that exact plan, and the executor
accepts only a matching receipt on the authorized execution path.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict

from planning.unreal_agent import UnrealOperation
from planning.unreal_task_planner import UnrealTaskPlan


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _operation_payload(operation: UnrealOperation) -> Dict[str, Any]:
    return {
        "capability": operation.capability.value,
        "kind": operation.kind.value,
        "name": operation.name,
        "arguments": dict(operation.arguments),
        "entity_ids": tuple(operation.entity_ids),
    }


def _plan_payload(plan: UnrealTaskPlan) -> Dict[str, Any]:
    return {
        "intent_id": plan.intent_id,
        "operations": [_operation_payload(operation) for operation in plan.operations],
    }


def _plan_digest(plan: UnrealTaskPlan) -> str:
    return hashlib.sha256(_canonical(_plan_payload(plan)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class UnrealPlanAuthorization:
    """Immutable proof that one exact Unreal task plan was authorized."""

    plan_digest: str
    authorization_id: str

    @classmethod
    def issue(cls, plan: UnrealTaskPlan, authorization_id: str) -> "UnrealPlanAuthorization":
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        return cls(_plan_digest(plan), authorization_id.strip())

    def matches(self, plan: UnrealTaskPlan) -> bool:
        return isinstance(plan, UnrealTaskPlan) and self.plan_digest == _plan_digest(plan)

    def snapshot(self) -> Dict[str, str]:
        return {
            "plan_digest": self.plan_digest,
            "authorization_id": self.authorization_id,
        }
