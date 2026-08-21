"""Task-specific verification helpers for verified Blender workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class VerificationDecision:
    ok: bool
    reason: str
    evidence: Mapping[str, Any]


def verify_object_location(
    result: Any,
    *,
    object_name: str,
    expected_location: tuple[float, float, float],
    tolerance: float = 1e-4,
) -> VerificationDecision:
    """Verify a fresh inspect_object_transform result against an expected location."""
    if getattr(result, "ok", False) is not True:
        return VerificationDecision(False, "inspection failed", {"result": result})

    details = getattr(result, "details", {})
    if not isinstance(details, Mapping):
        return VerificationDecision(False, "inspection details are not a mapping", {"details": details})

    actual_name = details.get("object_name")
    actual = details.get("location")
    if actual_name != object_name:
        return VerificationDecision(False, "inspected object does not match target", {"object_name": actual_name})
    if not isinstance(actual, (list, tuple)) or len(actual) != 3:
        return VerificationDecision(False, "inspection result has no valid location", {"location": actual})

    deltas = [abs(float(a) - float(e)) for a, e in zip(actual, expected_location)]
    passed = all(delta <= tolerance for delta in deltas)
    return VerificationDecision(
        passed,
        "object location matches expected state" if passed else "object location differs from expected state",
        {"object_name": object_name, "expected_location": list(expected_location), "actual_location": list(actual), "deltas": deltas, "tolerance": tolerance},
    )
