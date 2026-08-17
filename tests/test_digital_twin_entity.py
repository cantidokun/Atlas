import pytest

from planning.digital_twin_entity import DigitalTwinEntity, SemanticAttribute, create_entity
from planning.digital_twin_spatial import CoordinateFrame, DistanceUnit, SpatialPose, Vector3


def frame():
    return CoordinateFrame("atlas-world", DistanceUnit.METER, "z", "right")


def test_entity_is_engine_independent_and_semantic():
    entity = create_entity(
        "field-001",
        "goal-left-post",
        "goal_post",
        semantic_attributes=(
            SemanticAttribute("role", "goal structure"),
            SemanticAttribute("side", "left"),
        ),
        tags=frozenset({"Soccer", "Structural"}),
        spatial_pose=SpatialPose("atlas-world", Vector3(1.0, 2.0, 0.0)),
    )
    assert entity.twin_id == "field-001"
    assert entity.semantic_value("SIDE") == "left"
    assert entity.has_tag("soccer")
    assert entity.spatial_pose.frame_id == "atlas-world"


def test_empty_entity_identity_is_rejected():
    with pytest.raises(ValueError, match="entity_id"):
        create_entity("field-001", "", "goal_post")


def test_empty_semantic_attribute_is_rejected():
    with pytest.raises(ValueError, match="semantic attribute"):
        SemanticAttribute("", "goal structure")


def test_entity_cannot_parent_itself():
    with pytest.raises(ValueError, match="own parent"):
        create_entity("field-001", "goal-left", "goal", parent_entity_id="goal-left")


def test_entity_pose_parent_must_match_entity_parent():
    pose = SpatialPose(
        "atlas-world",
        Vector3(0.0, 0.0, 0.0),
        parent_entity_id="goal-a",
    )
    with pytest.raises(ValueError, match="parent"):
        create_entity(
            "field-001",
            "goal-left-post",
            "goal_post",
            spatial_pose=pose,
            parent_entity_id="goal-b",
        )


def test_entity_is_not_a_tool_representation():
    entity = DigitalTwinEntity("field-001", "field_surface", "field-001")
    assert not hasattr(entity, "blender_object")
    assert not hasattr(entity, "unreal_actor")
