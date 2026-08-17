import pytest

from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation


def evidence():
    return UnrealEvidence(
        operation_name="move_target_actor",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"location": {"x": 100, "y": 200, "z": 300}},
        source="unreal_editor",
    )


def test_evidence_accepts_explicit_operation_and_targets():
    value = evidence()
    assert validate_evidence_for_operation(
        value, "move_target_actor", ("FIELD_SURFACE",)
    ) == value


def test_evidence_rejects_operation_mismatch():
    with pytest.raises(ValueError, match="operation_name"):
        validate_evidence_for_operation(evidence(), "other_operation", ("FIELD_SURFACE",))


def test_evidence_rejects_target_mismatch():
    with pytest.raises(ValueError, match="entity_ids"):
        validate_evidence_for_operation(evidence(), "move_target_actor", ("OTHER_TARGET",))


def test_evidence_requires_source():
    with pytest.raises(ValueError, match="source"):
        UnrealEvidence(
            operation_name="move_target_actor",
            entity_ids=("FIELD_SURFACE",),
            observed_state={},
            source="",
        )
