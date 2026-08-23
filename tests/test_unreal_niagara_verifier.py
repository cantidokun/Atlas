import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_niagara_verifier import verify_niagara_variant
from planning.unreal_state_verifier import UnrealStateVerificationError


def _evidence(name="sparks"):
    return UnrealEvidence(
        operation_name="verify_niagara_variant",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"niagara": {"name": name}}},
        source="test",
        verified=False,
    )


def test_niagara_verifier_accepts_matching_state():
    assert verify_niagara_variant(_evidence(), {"name": "sparks"}).verified is False


def test_niagara_verifier_rejects_mismatch():
    with pytest.raises(UnrealStateVerificationError, match="does not match"):
        verify_niagara_variant(_evidence("smoke"), {"name": "sparks"})


def test_niagara_verifier_requires_exact_expected_shape():
    with pytest.raises(ValueError, match="exactly name"):
        verify_niagara_variant(_evidence(), {"name": "sparks", "enabled": True})
