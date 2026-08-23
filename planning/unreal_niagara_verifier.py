"""Semantic verification for Niagara post-write evidence."""

from typing import Any, Mapping

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_state_verifier import UnrealStateVerificationError


def verify_niagara_variant(
    evidence: UnrealEvidence,
    expected_variant: Mapping[str, object],
) -> UnrealEvidence:
    """Prove that fresh Unreal evidence contains the requested Niagara variant."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if not isinstance(expected_variant, Mapping) or set(expected_variant.keys()) != {"name"}:
        raise ValueError("expected_variant must contain exactly name")
    expected_name = expected_variant["name"]
    if not isinstance(expected_name, str) or not expected_name.strip():
        raise ValueError("expected_variant.name must be a non-empty string")

    for entity_id in evidence.entity_ids:
        try:
            entity_state = evidence.observed_state[entity_id]
        except (KeyError, TypeError):
            raise UnrealStateVerificationError(f"verification evidence is missing entity '{entity_id}'")
        if not isinstance(entity_state, Mapping):
            raise UnrealStateVerificationError(f"verification state for entity '{entity_id}' must be a mapping")
        state = entity_state.get("niagara")
        if not isinstance(state, Mapping):
            raise UnrealStateVerificationError(f"verification state for entity '{entity_id}' is missing niagara")
        actual_name = state.get("name")
        if actual_name != expected_name.strip():
            raise UnrealStateVerificationError(
                f"entity '{entity_id}' niagara name={actual_name!r} does not match expected {expected_name.strip()!r}"
            )
    return evidence
