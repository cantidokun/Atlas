"""Immutable authorization receipts for explicit Unreal task plans.

A receipt binds a concrete UnrealTaskPlan to an Atlas authorization identifier.
The receipt is intentionally separate from planning and execution: planning
proposes a plan, authorization approves that exact plan, and the executor
accepts only a matching receipt on the authorized execution path.

A production receipt may additionally bind one exact shot continuity by way of
its deterministic ``continuity_digest``. The continuity material is never
folded into ``plan_digest``, so every existing plan-only receipt keeps its
current identity and semantics: ``matches(plan)`` still means "this receipt
binds that exact plan", while ``matches(plan, continuity_digest=...)`` means
"this receipt binds that exact plan and that exact shot continuity" and fails
closed when the receipt carries no continuity binding at all.
"""

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Tuple

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


_CONTINUITY_DIGEST_LENGTH = 64


def _validate_continuity_digest(continuity_digest: Any) -> str:
    if not isinstance(continuity_digest, str) or len(continuity_digest) != _CONTINUITY_DIGEST_LENGTH:
        raise ValueError(
            "continuity_digest must be a canonical hexadecimal digest"
        )
    if any(character not in "0123456789abcdef" for character in continuity_digest):
        raise ValueError(
            "continuity_digest must be a canonical hexadecimal digest"
        )
    return continuity_digest


def _identity_material(values: Tuple[str, ...]) -> bytes:
    """Encode identity components unambiguously before hashing them."""
    encoded = []
    for value in values:
        raw = value.encode("utf-8")
        encoded.append(len(raw).to_bytes(8, "big"))
        encoded.append(raw)
    return b"".join(encoded)


@dataclass(frozen=True)
class UnrealPlanAuthorization:
    """Immutable proof that one exact Unreal task plan was authorized."""

    plan_digest: str
    authorization_id: str
    continuity_digest: Optional[str] = None

    @classmethod
    def issue(
        cls,
        plan: UnrealTaskPlan,
        authorization_id: str,
        *,
        continuity_digest: Optional[str] = None,
    ) -> "UnrealPlanAuthorization":
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        if continuity_digest is not None:
            _validate_continuity_digest(continuity_digest)
        return cls(_plan_digest(plan), authorization_id.strip(), continuity_digest)

    @property
    def continuity_bound(self) -> bool:
        """Whether this receipt also binds one exact shot continuity."""
        return self.continuity_digest is not None

    @property
    def authorization_digest(self) -> str:
        """Cryptographic identity of this exact plan authorization."""
        material = (self.plan_digest, self.authorization_id)
        if self.continuity_digest is not None:
            material = material + (self.continuity_digest,)
        return hashlib.sha256(_identity_material(material)).hexdigest()

    def matches(
        self,
        plan: UnrealTaskPlan,
        *,
        continuity_digest: Optional[str] = None,
    ) -> bool:
        """Whether this receipt binds the supplied plan, and any supplied continuity."""
        if not isinstance(plan, UnrealTaskPlan) or self.plan_digest != _plan_digest(plan):
            return False
        if continuity_digest is None:
            return True
        if not isinstance(continuity_digest, str) or self.continuity_digest is None:
            return False
        return hmac.compare_digest(self.continuity_digest, continuity_digest)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "plan_digest": self.plan_digest,
            "authorization_id": self.authorization_id,
            "continuity_digest": self.continuity_digest,
            "authorization_digest": self.authorization_digest,
        }
