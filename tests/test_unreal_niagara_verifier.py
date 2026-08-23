import pytest

from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_niagara_verifier import verify_niagara_variant
from planning.unreal_state_verifier import UnrealStateVerificationError


def _evidence(name):
    return UnrealEvidence(operation_name="verify_niagara_variant", entity_ids=("FIELD_SURFACE",), observed_state={"FIELD_SURFACE": {"niagara": {"variant": {"name": name}}}}, source="fake-unreal", verified=False)


def test_niagara_verifier_accepts_matching_fresh_state():
    assert verify_niagara_variant(_evidence("goal_burst"), {"name": "goal_burst"}) is not None


def test_niagara_verifier_rejects_mismatch():
    with pytest.raises(UnrealStateVerificationError, match="does not match"):
        verify_niagara_variant(_evidence("default"), {"name": "goal_burst"})
