"""Independent verification for Blueprint production evidence."""

from typing import Mapping

from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation


def verify_blueprint_state(evidence: UnrealEvidence, expected_compile_status: str) -> None:
    """Verify live Blueprint evidence against the requested compilation state."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be a UnrealEvidence instance")
    if not isinstance(expected_compile_status, str) or not expected_compile_status.strip():
        raise ValueError("expected_compile_status must be a non-empty string")
    validate_evidence_for_operation(evidence, "verify_blueprint_state", tuple(evidence.entity_ids))
    expected = expected_compile_status.strip().lower()
    for entity_id in evidence.entity_ids:
        state = evidence.observed_state.get(entity_id)
        if not isinstance(state, Mapping):
            raise ValueError("Blueprint evidence is missing the requested entity")
        blueprint = state.get("blueprint")
        if not isinstance(blueprint, Mapping):
            raise ValueError("Blueprint evidence is missing blueprint state")
        observed = blueprint.get("compile_status")
        if not isinstance(observed, str) or observed.strip().lower() != expected:
            raise ValueError("fresh Unreal Blueprint state does not match the requested compile status")
