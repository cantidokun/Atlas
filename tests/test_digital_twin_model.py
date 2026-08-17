import pytest

from planning.digital_twin_geometry import BoundingBox, GeometryKind, GeometryReference
from planning.digital_twin_measurements import Measurement, MeasurementStatus
from planning.digital_twin_provenance import ProvenanceRecord, ProvenanceSource
from planning.digital_twin_relationships import EntityRelationship, RelationshipType
from planning.digital_twin_spatial import Vector3
from planning.digital_twin_validation import ValidationRecord, ValidationState
from planning.digital_twin_variants import VariantKind, create_production_variant


def test_geometry_reference_is_engine_independent():
    geometry = GeometryReference(
        entity_id="goal-left-post",
        geometry_id="geom-001",
        kind=GeometryKind.MESH,
        representation_id="blender-field-r2",
        bounds=BoundingBox(Vector3(0, 0, 0), Vector3(0.1, 0.1, 2.4)),
    )
    assert geometry.entity_id == "goal-left-post"
    assert geometry.kind is GeometryKind.MESH


def test_invalid_bounding_box_is_rejected():
    with pytest.raises(ValueError):
        BoundingBox(Vector3(1, 0, 0), Vector3(0, 1, 1))


def test_relationship_cannot_self_reference():
    with pytest.raises(ValueError):
        EntityRelationship("goal", RelationshipType.PART_OF, "goal")


def test_measurement_respects_tolerance():
    passing = Measurement("goal", "width", 7.31, "m", 7.32, 0.02)
    failing = Measurement("goal", "width", 7.20, "m", 7.32, 0.02)
    assert passing.status() is MeasurementStatus.PASS
    assert failing.status() is MeasurementStatus.FAIL


def test_measurement_without_requirement_is_unverified():
    measurement = Measurement("goal", "width", 7.31, "m")
    assert measurement.status() is MeasurementStatus.UNVERIFIED


def test_provenance_tracks_source_and_operation():
    record = ProvenanceRecord(
        "goal-left-post",
        ProvenanceSource.PHOTOGRAMMETRY,
        "capture-003",
        "initial reconstruction",
        0.87,
    )
    assert record.source is ProvenanceSource.PHOTOGRAMMETRY
    assert record.confidence == 0.87


def test_provenance_confidence_is_bounded():
    with pytest.raises(ValueError):
        ProvenanceRecord("goal", ProvenanceSource.BLENDER, "run-1", "cleanup", 1.1)


def test_validation_is_attribute_level():
    record = ValidationRecord("goal-left-post", "dimensions", ValidationState.VALIDATED, "evidence-42")
    assert record.state is ValidationState.VALIDATED


def test_production_variant_cannot_be_canonical():
    variant = create_production_variant("field-001", "liquid-shot", "field-001-r4")
    assert variant.kind is VariantKind.PRODUCTION
    with pytest.raises(ValueError):
        create_production_variant("field-001", "bad", "field-001-r4", VariantKind.CANONICAL)
