import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_state_verifier import UnrealStateVerificationError, verify_actor_rotation


def _evidence(rotation):
    return UnrealEvidence(
        operation_name="verify_target_actor_mapping",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"rotation": rotation}},
        source="unreal",
        verified=False,
    )


def test_verify_actor_rotation_accepts_matching_state_with_tolerance():
    evidence = _evidence({"pitch": 11.00001, "yaw": 37.0, "roll": -9.0})

    result = verify_actor_rotation(
        evidence,
        {"pitch": 11.0, "yaw": 37.0, "roll": -9.0},
    )

    assert result is evidence


def test_verify_actor_rotation_rejects_mismatched_axis():
    evidence = _evidence({"pitch": 11.0, "yaw": 37.5, "roll": -9.0})

    with pytest.raises(UnrealStateVerificationError, match="rotation yaw"):
        verify_actor_rotation(
            evidence,
            {"pitch": 11.0, "yaw": 37.0, "roll": -9.0},
        )


def test_verify_actor_rotation_rejects_missing_rotation_state():
    evidence = UnrealEvidence(
        operation_name="verify_target_actor_mapping",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"location": {"x": 0, "y": 0, "z": 0}}},
        source="unreal",
        verified=False,
    )

    with pytest.raises(UnrealStateVerificationError, match="missing rotation"):
        verify_actor_rotation(
            evidence,
            {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
        )


def test_verify_actor_rotation_requires_exact_axes():
    evidence = _evidence({"pitch": 0.0, "yaw": 0.0, "roll": 0.0})

    with pytest.raises(ValueError, match="exactly pitch, yaw, roll"):
        verify_actor_rotation(evidence, {"pitch": 0.0, "yaw": 0.0})
