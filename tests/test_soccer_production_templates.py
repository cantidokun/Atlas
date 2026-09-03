import pytest

from planning.soccer_production_templates import BroadcastGoalPreparationTemplate


def test_broadcast_goal_template_builds_reusable_dependent_fragments():
    template = BroadcastGoalPreparationTemplate(
        file_name="scene.blend",
        object_name="Goal_Left_post",
        target_location=(1.0, 2.0, 3.0),
        target_rotation=(0.0, 0.0, 15.0),
    )

    fragments = template.fragments()

    assert template.name == "broadcast-goal-preparation"
    assert template.objective == "Prepare the soccer goal for a broadcast shot."
    assert template.fragment_names() == ["position-goal", "orient-goal"]
    assert fragments[1].depends_on == ("position-goal",)
    assert fragments[1].actions[0].dependency_names() == ("position_goal",)
    assert fragments[0].actions[0].arguments["location"] == [1.0, 2.0, 3.0]
    assert fragments[1].actions[0].arguments["rotation_degrees"] == [0.0, 0.0, 15.0]


def test_broadcast_goal_template_instances_are_independent():
    first = BroadcastGoalPreparationTemplate(
        file_name="first.blend",
        object_name="Goal_A",
        target_location=(1.0, 2.0, 3.0),
        target_rotation=(0.0, 0.0, 10.0),
    )
    second = BroadcastGoalPreparationTemplate(
        file_name="second.blend",
        object_name="Goal_B",
        target_location=(4.0, 5.0, 6.0),
        target_rotation=(0.0, 0.0, 20.0),
    )

    first_fragments = first.fragments()
    second_fragments = second.fragments()

    assert first_fragments[0].actions[0].arguments["file_name"] == "first.blend"
    assert second_fragments[0].actions[0].arguments["file_name"] == "second.blend"
    assert first_fragments[0].actions[0].arguments["location"] != second_fragments[0].actions[0].arguments["location"]
    assert first_fragments[1].actions[0].arguments["object_name"] == "Goal_A"
    assert second_fragments[1].actions[0].arguments["object_name"] == "Goal_B"


def test_broadcast_goal_template_rejects_invalid_transform_shapes():
    with pytest.raises(ValueError, match="target_location"):
        BroadcastGoalPreparationTemplate(
            file_name="scene.blend",
            object_name="Goal_Left_post",
            target_location=(1.0, 2.0),
            target_rotation=(0.0, 0.0, 15.0),
        )

    with pytest.raises(ValueError, match="target_rotation"):
        BroadcastGoalPreparationTemplate(
            file_name="scene.blend",
            object_name="Goal_Left_post",
            target_location=(1.0, 2.0, 3.0),
            target_rotation=(0.0, 15.0),
        )
