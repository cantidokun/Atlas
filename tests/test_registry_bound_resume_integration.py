import pytest

from planning.production_resume_integrity_gate import (
    ProductionResumeCheckpoint,
    ProductionResumeRequest,
    validate_production_resume,
)


def _identity(**overrides):
    values = {
        "sequence_id": "sequence-1",
        "plan_id": "plan-1",
        "digital_twin_revision": "twin-r7",
    }
    values.update(overrides)
    return values


def test_resume_gate_identity_matches_registry_bound_checkpoint():
    checkpoint = ProductionResumeCheckpoint(**_identity(completed_operation_index=2))
    request = ProductionResumeRequest(**_identity())
    validate_production_resume(checkpoint, request)


def test_registry_revision_change_is_detected_before_resume():
    checkpoint = ProductionResumeCheckpoint(**_identity(completed_operation_index=2))
    request = ProductionResumeRequest(**_identity(digital_twin_revision="twin-r8"))
    with pytest.raises(ValueError, match="Digital Twin revision"):
        validate_production_resume(checkpoint, request)
