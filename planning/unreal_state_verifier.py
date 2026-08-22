"""Semantic verification for Unreal post-write evidence."""

from math import isclose
from typing import Any, Mapping

from planning.unreal_evidence_contract import UnrealEvidence


class UnrealStateVerificationError(ValueError):
    """Raised when post-write Unreal evidence does not prove the requested state."""


def _extract_state_component(
    observed_state: Mapping[str, Any],
    entity_id: str,
    component: str,
) -> Mapping[str, Any]:
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
    value = entity_state.get(component)
    if not isinstance(value, Mapping):
        raise UnrealStateVerificationError(
            f"verification state for entity '{entity_id}' is missing {component}"
        )
    return value


def _validate_expected_vector(
    expected: Mapping[str, float],
    axes: tuple[str, ...],
    name: str,
) -> None:
    if not isinstance(expected, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if set(expected) != set(axes):
        raise ValueError(f"{name} must contain exactly {', '.join(axes)}")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in expected.values()):
        raise TypeError(f"{name} values must be numeric")


def _verify_vector(
    evidence: UnrealEvidence,
    expected: Mapping[str, float],
    *,
    component: str,
    axes: tuple[str, ...],
    name: str,
    tolerance: float,
) -> UnrealEvidence:
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if tolerance < 0:
        raise ValueError("tolerance must not be negative")
    _validate_expected_vector(expected, axes, name)

    for entity_id in evidence.entity_ids:
        actual_state = _extract_state_component(evidence.observed_state, entity_id, component)
        for axis in axes:
            actual = actual_state.get(axis)
            expected_value = expected[axis]
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                raise UnrealStateVerificationError(
                    f"verification state for entity '{entity_id}' has non-numeric {component} {axis}"
                )
            if not isclose(float(actual), float(expected_value), rel_tol=0.0, abs_tol=tolerance):
                raise UnrealStateVerificationError(
                    f"entity '{entity_id}' {component} {axis}={actual} does not match "
                    f"expected {expected_value} within tolerance {tolerance}"
                )

    return evidence


def verify_actor_location(
    evidence: UnrealEvidence,
    expected_location: Mapping[str, float],
    *,
    tolerance: float = 1e-4,
) -> UnrealEvidence:
    """Prove that Unreal's observed actor location matches the requested state."""
    return _verify_vector(
        evidence,
        expected_location,
        component="location",
        axes=("x", "y", "z"),
        name="expected_location",
        tolerance=tolerance,
    )


def verify_actor_rotation(
    evidence: UnrealEvidence,
    expected_rotation: Mapping[str, float],
    *,
    tolerance: float = 1e-4,
) -> UnrealEvidence:
    """Prove that Unreal's observed actor rotation matches the requested state."""
    return _verify_vector(
        evidence,
        expected_rotation,
        component="rotation",
        axes=("pitch", "yaw", "roll"),
        name="expected_rotation",
        tolerance=tolerance,
    )
