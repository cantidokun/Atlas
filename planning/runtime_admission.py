"""Fail-closed admission gate for autonomous runtime continuation."""

from dataclasses import dataclass
from typing import Any, Mapping

from planning.runtime_context import RuntimeContext


class RuntimeAdmissionError(RuntimeError):
    """Raised when runtime continuation cannot be admitted safely."""


@dataclass(frozen=True)
class RuntimeAdmission:
    stable_fingerprint: str
    plan_digest: str
    state_digest: str


def admit_runtime_continuation(
    context: RuntimeContext,
    *,
    authorized_plan_digest: str,
    persisted_state: Mapping[str, Any],
    persisted_stable_fingerprint: str,
    persisted_plan_digest: str,
    persisted_state_digest: str,
    expected_state_digest: str,
) -> RuntimeAdmission:
    """Admit continuation only when every persisted identity matches live state."""
    current_fingerprint = context.stable_fingerprint()
    if persisted_stable_fingerprint != current_fingerprint:
        raise RuntimeAdmissionError("stable runtime context fingerprint mismatch")
    if not authorized_plan_digest or persisted_plan_digest != authorized_plan_digest:
        raise RuntimeAdmissionError("authorized plan digest mismatch")
    if persisted_state_digest != expected_state_digest:
        raise RuntimeAdmissionError("persisted runtime state digest mismatch")
    if not isinstance(persisted_state, Mapping):
        raise RuntimeAdmissionError("persisted runtime state is invalid")
    return RuntimeAdmission(
        stable_fingerprint=current_fingerprint,
        plan_digest=authorized_plan_digest,
        state_digest=expected_state_digest,
    )
