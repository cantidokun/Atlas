import pytest

from planning.soccer_production_workflows import (
    SoccerGoalTransformWorkflowSpec,
    build_broadcast_goal_preparation,
)


def test_goal_workflow_template_builds_canonical_task(tmp_path):
    production = build_broadcast_goal_preparation(
        blend_file=tmp_path / "scene.blend",
        object_name="Goal_Left_post",
        target_location=(0.25, 5.302, 0.0),
        target_rotation=(0.0, 0.0, 15.0),
    )

    assert production.name == "prepare-broadcast-goal"
    assert production.domain == "soccer-production"
    assert [action.name for action in production.actions] == ["position_goal", "orient_goal"]
    assert production.actions[1].dependency_names() == ("position_goal",)
    assert production.compile().actions == production.actions
    assert production.snapshot()["metadata"]["fragments"] == ["position-goal", "orient-goal"]


def test_goal_workflow_spec_rejects_invalid_transform_shape(tmp_path):
    with pytest.raises(ValueError, match="exactly three values"):
        SoccerGoalTransformWorkflowSpec(
            name="workflow",
            objective="Prepare a soccer goal.",
            blend_file=tmp_path / "scene.blend",
            object_name="Goal_Left_post",
            target_location=(0.0, 1.0),
            target_rotation=(0.0, 0.0, 15.0),
        )


def test_goal_workflow_template_normalizes_numeric_sequences(tmp_path):
    production = build_broadcast_goal_preparation(
        blend_file=tmp_path / "scene.blend",
        object_name="Goal_Left_post",
        target_location=["0.25", 5, 0],
        target_rotation=[0, 0, "15"],
    )

    assert production.actions[0].arguments["location"] == [0.25, 5.0, 0.0]
    assert production.actions[1].arguments["rotation_degrees"] == [0.0, 0.0, 15.0]
