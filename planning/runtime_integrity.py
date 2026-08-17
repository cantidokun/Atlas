"""Fail-closed integrity checks for autonomous runtime continuation."""

from dataclasses import dataclass
from typing import Any, Dict

from .runtime_context import RuntimeContext


@dataclass(frozen=True)
class RuntimeIntegrity:
    """Identity of the state that was authorized for continuation."""

    stable_fingerprint: str
    plan_digest: str
    state_digest: str

    def validate(
        self,
        context: RuntimeContext,
        *,
        plan_digest: str,
        state_digest: str,
    ) -> bool:
        """Return True only when every authoritative identity still matches."""
        return (
            context.matches_stable_fingerprint(self.stable_fingerprint)
            and plan_digest == self.plan_digest
            and state_digest == self.state_digest
        )

    def to_dict(self) -> Dict[str, str]:
        """Return a persistence-safe representation of the authorization."""
        return {
            "stable_fingerprint": self.stable_fingerprint,
            "plan_digest": self.plan_digest,
            "state_digest": self.state_digest,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "RuntimeIntegrity":
        """Restore an integrity receipt and reject malformed persisted data."""
        if not isinstance(value, dict):
            raise RuntimeError("runtime integrity receipt must be an object")
        fields = ("stable_fingerprint", "plan_digest", "state_digest")
        if any(not isinstance(value.get(field), str) or not value[field] for field in fields):
            raise RuntimeError("runtime integrity receipt is incomplete")
        return cls(*(value[field] for field in fields))


def authorize_continuation(
    context: RuntimeContext,
    *,
    plan_digest: str,
    state_digest: str,
) -> RuntimeIntegrity:
    """Capture the exact identities required for a future continuation."""
    if not plan_digest or not state_digest:
        raise ValueError("plan_digest and state_digest are required.")
    return RuntimeIntegrity(
        stable_fingerprint=context.stable_fingerprint(),
        plan_digest=plan_digest,
        state_digest=state_digest,
    )


def require_continuation_integrity(
    authorization: RuntimeIntegrity,
    context: RuntimeContext,
    *,
    plan_digest: str,
    state_digest: str,
) -> None:
    """Fail closed if any continuation identity has changed."""
    if not authorization.validate(
        context,
        plan_digest=plan_digest,
        state_digest=state_digest,
    ):
        raise RuntimeError("runtime continuation integrity check failed")
