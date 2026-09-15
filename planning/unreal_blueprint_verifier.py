"""Independent verification for Blueprint production evidence.

Expected state is taken only from the authorization-bound plan: the authorized asset
path and compile status come from the VERIFY operation's own arguments, and the
expected metadata pair comes from the paired authorized ``set_blueprint_metadata``
operation when the plan contains one. Returned evidence is never treated as an
expectation.
"""

from typing import Any, Mapping, Tuple

from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation


def _normalize_expected_metadata(expected_metadata: Mapping[str, Any]) -> Tuple[str, str]:
    """Normalize the authorized metadata expectation, failing closed if malformed."""
    if not isinstance(expected_metadata, Mapping) or set(expected_metadata) != {"metadata_key", "metadata_value"}:
        raise ValueError("expected_metadata must contain exactly metadata_key and metadata_value")
    expected_key = expected_metadata["metadata_key"]
    expected_value = expected_metadata["metadata_value"]
    if not isinstance(expected_key, str) or not expected_key.strip():
        raise ValueError("expected_metadata.metadata_key must be a non-empty string")
    if not isinstance(expected_value, str) or not expected_value.strip():
        raise ValueError("expected_metadata.metadata_value must be a non-empty string")
    return expected_key.strip(), expected_value.strip()


def verify_blueprint_state(
    evidence: UnrealEvidence,
    expected_compile_status: str,
    expected_asset_path: str,
    expected_metadata: Mapping[str, Any] = None,
) -> UnrealEvidence:
    """Prove that fresh Blueprint evidence matches authorized expected state.

    Compares engine-observed Blueprint state against the authorized asset path, the
    authorized compile status and, when the plan carries a paired authorized metadata
    write, the authorized metadata key/value. Unrelated metadata keys are tolerated;
    missing or mismatching expected state fails closed.
    """
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if not isinstance(expected_compile_status, str) or not expected_compile_status.strip():
        raise ValueError("expected_compile_status must be a non-empty string")
    if not isinstance(expected_asset_path, str) or not expected_asset_path.strip():
        raise ValueError("expected_asset_path must be a non-empty Unreal package path")
    expected_status = expected_compile_status.strip().lower()
    expected_asset = expected_asset_path.strip()
    expected_key = expected_value = None
    if expected_metadata is not None:
        expected_key, expected_value = _normalize_expected_metadata(expected_metadata)
    validate_evidence_for_operation(evidence, "verify_blueprint_state", tuple(evidence.entity_ids))
    for entity_id in evidence.entity_ids:
        state = evidence.observed_state.get(entity_id)
        if not isinstance(state, Mapping):
            raise ValueError("Blueprint evidence is missing the requested entity")
        blueprint = state.get("blueprint")
        if not isinstance(blueprint, Mapping):
            raise ValueError("Blueprint evidence is missing blueprint state")
        observed_asset_path = blueprint.get("asset_path")
        if not isinstance(observed_asset_path, str) or observed_asset_path != expected_asset:
            raise ValueError("fresh Unreal Blueprint state does not match the authorized asset path")
        observed = blueprint.get("compile_status")
        if not isinstance(observed, str) or observed.strip().lower() != expected_status:
            raise ValueError("fresh Unreal Blueprint state does not match the requested compile status")
        if expected_key is not None:
            metadata = blueprint.get("metadata")
            if not isinstance(metadata, Mapping):
                raise ValueError("Blueprint evidence is missing blueprint metadata")
            if expected_key not in metadata:
                raise ValueError(f"Blueprint evidence is missing the authorized metadata key {expected_key!r}")
            observed_value = metadata[expected_key]
            if not isinstance(observed_value, str):
                raise ValueError(f"Blueprint metadata {expected_key!r} must be a string")
            if observed_value != expected_value:
                raise ValueError(
                    f"Blueprint metadata {expected_key!r}={observed_value!r} does not match expected {expected_value!r}"
                )
    return evidence
