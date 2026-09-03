import pytest

from planning.soccer_production_catalog import (
    available_soccer_production_workflows,
    build_soccer_production_workflow,
    get_soccer_production_workflow,
)


def test_catalog_exposes_stable_broadcast_goal_workflow():
    workflows = available_soccer_production_workflows()

    assert [workflow.name for workflow in workflows] == ["broadcast-goal-preparation"]
    assert workflows[0].objective == "Prepare the soccer goal for a broadcast shot."
    assert workflows[0].template_name == "BroadcastGoalPreparationTemplate"
    assert workflows[0].version == 1
    assert workflows[0].required_parameters == (
        "file_name",
        "object_name",
        "target_location",
        "target_rotation",
    )


def test_catalog_resolves_workflow_by_exact_name():
    workflow = get_soccer_production_workflow("broadcast-goal-preparation")

    assert workflow.snapshot() == {
        "name": "broadcast-goal-preparation",
        "objective": "Prepare the soccer goal for a broadcast shot.",
        "template_name": "BroadcastGoalPreparationTemplate",
        "required_parameters": [
            "file_name",
            "object_name",
            "target_location",
            "target_rotation",
        ],
        "parameter_kinds": {
            "file_name": "string",
            "object_name": "string",
            "target_location": "vector3",
            "target_rotation": "vector3",
        },
        "version": 1,
    }

    with pytest.raises(KeyError, match="unknown soccer production workflow"):
        get_soccer_production_workflow("unknown-workflow")


def test_catalog_builds_only_the_declared_template():
    template = build_soccer_production_workflow(
        "broadcast-goal-preparation",
        {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "target_location": [1.0, 2.0, 3.0],
            "target_rotation": [0.0, 0.0, 15.0],
        },
    )

    assert template.name == "broadcast-goal-preparation"
    assert template.target_location == (1.0, 2.0, 3.0)
    assert template.target_rotation == (0.0, 0.0, 15.0)
    assert template.production_task().compile().metadata["workflow_template"] == "broadcast-goal-preparation"


def test_catalog_rejects_missing_and_unexpected_parameters():
    with pytest.raises(ValueError, match="missing required parameters"):
        build_soccer_production_workflow(
            "broadcast-goal-preparation",
            {
                "file_name": "scene.blend",
                "object_name": "Goal_Left_post",
                "target_location": [1.0, 2.0, 3.0],
            },
        )

    with pytest.raises(ValueError, match="unexpected parameters"):
        build_soccer_production_workflow(
            "broadcast-goal-preparation",
            {
                "file_name": "scene.blend",
                "object_name": "Goal_Left_post",
                "target_location": [1.0, 2.0, 3.0],
                "target_rotation": [0.0, 0.0, 15.0],
                "execute": True,
            },
        )


def test_catalog_rejects_invalid_spec_versions():
    from planning.soccer_production_catalog import SoccerProductionWorkflowSpec

    with pytest.raises(ValueError, match="positive integer"):
        SoccerProductionWorkflowSpec(
            name="invalid",
            objective="Prepare a soccer production workflow.",
            template_name="ExampleTemplate",
            required_parameters=("file_name",),
            parameter_kinds=(("file_name", "string"),),
            version=0,
        )

    with pytest.raises(ValueError, match="positive integer"):
        SoccerProductionWorkflowSpec(
            name="invalid",
            objective="Prepare a soccer production workflow.",
            template_name="ExampleTemplate",
            required_parameters=("file_name",),
            parameter_kinds=(("file_name", "string"),),
            version=True,
        )
