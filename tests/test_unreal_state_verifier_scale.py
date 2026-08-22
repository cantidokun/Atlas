import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_state_verifier import UnrealStateVerificationError, verify_actor_scale


def _evidence(scale):
    return UnrealEvidence(
        operation_name="verify_target_actor_mapping",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"scale": scale}},
        source="unreal",
        verified=False,
    )


def test_verify_actor_scale_accepts_matching_state_with_tolerance():
    evidence = _evidence({"x": 1.00001, "y": 0.75, "z": 2.0})
    assert verify_actor_scale(evidence, {"x": 1.0, "y": 0.75, "z": 2.0}) is evidence


def test_verify_actor_scale_rejects_mismatched_axis():
    evidence = _evidence({"x": 1.0, "y": 0.8, "z": 2.0})
    with pytest.raises(UnrealStateVerificationError, match="scale y"):
        verify_actor_scale(evidence, {"x": 1.0, "y": 0.75, "z": 2.0})


def test_verify_actor_scale_rejects_missing_scale_state():
    evidence = UnrealEvidence(
        operation_name="verify_target_actor_mapping",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"rotation": {"pitch": 0, "yaw": 0, "roll": 0}}},
        source="unreal",
        verified=False,
    )
    with pytest.raises(UnrealStateVerificationError, match="missing scale"):
        verify_actor_scale(evidence, {"x": 1.0, "y": 1.0, "z": 1.0})


def test_verify_actor_scale_requires_exact_axes():
    evidence = _evidence({"x": 1.0, "y": 1.0, "z": 1.0})
    with pytest.raises(ValueError, match="exactly x, y, z"):
        verify_actor_scale(evidence, {"x": 1.0, "y": 1.0})
