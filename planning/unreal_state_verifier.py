"""Semantic verification for Unreal post-write evidence."""

from math import isclose
from typing import Any, Mapping, Tuple

from planning.unreal_evidence_contract import UnrealEvidence


class UnrealStateVerificationError(ValueError):
    """Raised when post-write Unreal evidence does not prove the requested state."""


def _extract_location(observed_state: Mapping[str, Any], entity_id: str) -> Mapping[str, Any]:
    try:
        entity_state = observed_state[entity_id]
    except (KeyError, TypeError):
        raise UnrealStateVerificationError(
            f"verification evidence is missing entity '{entity_id}'"
        )
    if not isinstance(entity_state, Mapping):
        raise UnrealStateVerificationError(
            f"verification state for entity '{entity_id}' must be a mapping"
        )
    location = entity_state.get("location")
    if not isinstance(location, Mapping):
        raise UnrealStateVerificationError(
            f"verification state for entity '{entity_id}' is missing location"
        )
    return location


def verify_actor_location(
    evidence: UnrealEvidence,
    expected_location: Mapping[str, float],
    *,
    tolerance: float = 1e-4,
) -> UnrealEvidence:
    """Prove that Unreal's observed actor location matches the requested state."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if not isinstance(expected_location, Mapping):
        raise TypeError("expected_location must be a mapping")
    if set(expected_location) != {"x", "y", "z"}:
        raise ValueError("expected_location must contain exactly x, y, and z")
    if tolerance < 0:
        raise ValueError("tolerance must not be negative")

    for entity_id in evidence.entity_ids:
        location = _extract_location(evidence.observed_state, entity_id)
        for axis in ("x", "y", "z"):
            actual = location.get(axis)
            expected = expected_location[axis]
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                raise UnrealStateVerificationError(
                    f"verification state for entity '{entity_id}' has non-numeric {axis}"
                )
            if isinstance(expected, bool) or not isinstance(expected, (int, float)):
                raise TypeError("expected_location coordinates must be numeric")
            if not isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance):
                raise UnrealStateVerificationError(
                    f"entity '{entity_id}' location {axis}={actual} does not match "
                    f"expected {expected} within tolerance {tolerance}"
                )

    return evidence
