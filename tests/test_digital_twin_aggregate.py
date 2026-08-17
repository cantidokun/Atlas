import pytest

from planning.digital_twin_aggregate import DigitalTwinAggregate
from planning.digital_twin_entity import DigitalTwinEntity
from planning.digital_twin_identity import DigitalTwinIdentity
from planning.digital_twin_revision import RevisionKind, create_revision


def identity(twin_id="field-001"):
    return DigitalTwinIdentity(twin_id, "soccer_field", ())


def revision(twin_id="field-001"):
    current_identity = identity(twin_id)
    return create_revision(current_identity, f"{twin_id}-r1", 1, RevisionKind.RECONSTRUCTION)


def test_aggregate_owns_entities_for_one_revision():
    entity = DigitalTwinEntity("goal-left", "goal", "field-001")
    aggregate = DigitalTwinAggregate("field-001", revision(), (entity,))
    assert aggregate.entity("goal-left") is entity


def test_cross_twin_entity_is_rejected():
    entity = DigitalTwinEntity("goal-left", "goal", "field-002")
    with pytest.raises(ValueError, match="different Digital Twin"):
        DigitalTwinAggregate("field-001", revision(), (entity,))


def test_cross_twin_revision_is_rejected():
    with pytest.raises(ValueError, match="different Digital Twin"):
        DigitalTwinAggregate("field-001", revision("field-002"))


def test_missing_entity_is_explicit():
    aggregate = DigitalTwinAggregate("field-001", revision())
    with pytest.raises(KeyError):
        aggregate.entity("missing")
