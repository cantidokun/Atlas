import pytest

from planning.production_resume_integrity_gate import (
    ProductionResumeCheckpoint,
    ProductionResumeRequest,
    validate_production_resume,
)


def checkpoint(**overrides):
    values = {
        "sequence_id": "sequence-1",
        "plan_id": "plan-1",
        "digital_twin_revision": "twin-r7",
        "completed_operation_index": 2,
    }
    values.update(overrides)
    return ProductionResumeCheckpoint(**values)


def request(**overrides):
    values = {
        "sequence_id": "sequence-1",
        "plan_id": "plan-1",
        "digital_twin_revision": "twin-r7",
    }
    values.update(overrides)
    return ProductionResumeRequest(**values)


def test_matching_checkpoint_is_resumable():
    validate_production_resume(checkpoint(), request())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sequence_id", "sequence-2", "sequence_id"),
        ("plan_id", "plan-2", "plan_id"),
        ("digital_twin_revision", "twin-r8", "Digital Twin revision"),
    ],
)
def test_identity_mismatch_fails_closed(field, value, message):
    with pytest.raises(ValueError, match=message):
        validate_production_resume(checkpoint(), request(**{field: value}))


def test_checkpoint_rejects_negative_index_below_sentinel():
    with pytest.raises(ValueError, match="completed_operation_index"):
        checkpoint(completed_operation_index=-2)


def test_checkpoint_rejects_boolean_operation_index():
    with pytest.raises(TypeError, match="completed_operation_index"):
        checkpoint(completed_operation_index=True)


def test_gate_rejects_wrong_input_types():
    with pytest.raises(TypeError, match="checkpoint"):
        validate_production_resume(object(), request())
    with pytest.raises(TypeError, match="request"):
        validate_production_resume(checkpoint(), object())
