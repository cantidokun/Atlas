import pytest

from planning.digital_twin_spatial import (
    CoordinateFrame,
    DistanceUnit,
    Quaternion,
    SpatialPose,
    Vector3,
)


def test_coordinate_frame_is_engine_agnostic():
    frame = CoordinateFrame("field-001-atlas", DistanceUnit.METER, "z", "right")
    assert frame.frame_id == "field-001-atlas"
    assert frame.unit == DistanceUnit.METER
    assert frame.up_axis == "z"
    assert frame.handedness == "right"
    assert frame.origin == Vector3(0.0, 0.0, 0.0)


def test_spatial_pose_uses_atlas_frame_and_optional_parent():
    pose = SpatialPose(
        "field-001-atlas",
        Vector3(10.0, 2.5, 0.0),
        parent_entity_id="field-001-goal-left",
    )
    assert pose.frame_id == "field-001-atlas"
    assert pose.position == Vector3(10.0, 2.5, 0.0)
    assert pose.parent_entity_id == "field-001-goal-left"


def test_non_finite_vectors_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        Vector3(float("nan"), 0.0, 0.0)


def test_invalid_coordinate_frame_is_rejected():
    with pytest.raises(ValueError, match="up_axis"):
        CoordinateFrame("field-001-atlas", DistanceUnit.METER, "q", "right")

    with pytest.raises(ValueError, match="handedness"):
        CoordinateFrame("field-001-atlas", DistanceUnit.METER, "z", "unknown")


def test_zero_quaternion_is_rejected():
    with pytest.raises(ValueError, match="non-zero magnitude"):
        Quaternion(0.0, 0.0, 0.0, 0.0)


def test_empty_parent_is_rejected():
    with pytest.raises(ValueError, match="parent_entity_id"):
        SpatialPose("field-001-atlas", Vector3(0.0, 0.0, 0.0), parent_entity_id=" ")
