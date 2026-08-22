"""Semantic verification for Unreal material post-write evidence."""

from typing import Any, Mapping

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_state_verifier import UnrealStateVerificationError


def verify_material_variant(
    evidence: UnrealEvidence,
    expected_material_variant: Mapping[str, Any],
) -> UnrealEvidence:
    """Prove that fresh Unreal evidence contains the requested material variant."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if not isinstance(expected_material_variant, Mapping):
        raise TypeError("expected_material_variant must be a mapping")
    if set(expected_material_variant) != {"name"}:
        raise ValueError("expected_material_variant must contain exactly name")
    expected_name = expected_material_variant["name"]
    if not isinstance(expected_name, str) or not expected_name.strip():
        raise ValueError("expected_material_variant.name must be a non-empty string")

    for entity_id in evidence.entity_ids:
        try:
            entity_state = evidence.observed_state[entity_id]
        except (KeyError, TypeError):
            raise UnrealStateVerificationError(
                f"verification evidence is missing entity '{entity_id}'"
            )
        if not isinstance(entity_state, Mapping):
            raise UnrealStateVerificationError(
                f"verification state for entity '{entity_id}' must be a mapping"
            )
        material_state = entity_state.get("material")
        if not isinstance(material_state, Mapping):
            raise UnrealStateVerificationError(
                f"verification state for entity '{entity_id}' is missing material"
            )
        variant = material_state.get("variant")
        if not isinstance(variant, Mapping):
            raise UnrealStateVerificationError(
                f"verification state for entity '{entity_id}' is missing material variant"
            )
        actual_name = variant.get("name")
        if actual_name != expected_name.strip():
            raise UnrealStateVerificationError(
                f"entity '{entity_id}' material variant={actual_name!r} does not match "
                f"expected {expected_name.strip()!r}"
            )

    return evidence
