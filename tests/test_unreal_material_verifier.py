import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_material_verifier import verify_material_variant
from planning.unreal_state_verifier import UnrealStateVerificationError


def _evidence(name="blue"):
    return UnrealEvidence(
        operation_name="verify_material_variant",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "FIELD_SURFACE": {
                "material": {"variant": {"name": name}},
            }
        },
        source="fake-unreal",
        verified=False,
    )


def test_material_verifier_accepts_matching_variant():
    evidence = verify_material_variant(_evidence(), {"name": "blue"})
    assert evidence.verified is False


def test_material_verifier_rejects_mismatched_variant():
    with pytest.raises(UnrealStateVerificationError, match="material variant"):
        verify_material_variant(_evidence("red"), {"name": "blue"})


def test_material_verifier_requires_material_state():
    evidence = UnrealEvidence(
        operation_name="verify_material_variant",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {}},
        source="fake-unreal",
        verified=False,
    )
    with pytest.raises(UnrealStateVerificationError, match="missing material"):
        verify_material_variant(evidence, {"name": "blue"})


def test_material_verifier_rejects_invalid_expected_variant():
    with pytest.raises(ValueError, match="exactly name"):
        verify_material_variant(_evidence(), {"name": "blue", "unused": True})
