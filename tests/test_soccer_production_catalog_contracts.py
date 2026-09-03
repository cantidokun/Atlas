import pytest

from planning.soccer_production_catalog import (
    SoccerProductionWorkflowSpec,
    available_soccer_production_workflows,
    build_soccer_production_workflow,
    get_soccer_production_workflow,
)


def test_catalog_descriptors_are_immutable_and_stable():
    workflow = get_soccer_production_workflow("broadcast-goal-preparation")

    with pytest.raises(Exception):
        workflow.name = "mutated"

    assert workflow.version == 1
    assert available_soccer_production_workflows()[0].snapshot() == workflow.snapshot()


def test_catalog_rejects_duplicate_parameter_contract_entries():
    with pytest.raises(ValueError, match="parameters must be unique"):
        SoccerProductionWorkflowSpec(
            name="invalid",
            objective="Prepare a soccer production workflow.",
            template_name="ExampleTemplate",
            required_parameters=("file_name", "file_name"),
        )


def test_catalog_rejects_invalid_versions():
    with pytest.raises(ValueError, match="positive integer"):
        SoccerProductionWorkflowSpec(
            name="invalid",
            objective="Prepare a soccer production workflow.",
            template_name="ExampleTemplate",
            required_parameters=("file_name",),
            version=0,
        )

    with pytest.raises(ValueError, match="positive integer"):
        SoccerProductionWorkflowSpec(
            name="invalid",
            objective="Prepare a soccer production workflow.",
            template_name="ExampleTemplate",
            required_parameters=("file_name",),
            version=True,
        )


def test_catalog_resolves_supported_and_rejects_unsupported_versions():
    workflow = get_soccer_production_workflow("broadcast-goal-preparation", version=1)
    assert workflow.version == 1

    with pytest.raises(KeyError, match="unsupported version"):
        get_soccer_production_workflow("broadcast-goal-preparation", version=2)


def test_catalog_builder_preserves_template_validation_boundary():
    with pytest.raises(ValueError, match="finite numeric"):
        build_soccer_production_workflow(
            "broadcast-goal-preparation",
            {
                "file_name": "scene.blend",
                "object_name": "Goal_Left_post",
                "target_location": [0.0, float("inf"), 0.0],
                "target_rotation": [0.0, 0.0, 15.0],
            },
        )

    with pytest.raises(ValueError, match="three values"):
        build_soccer_production_workflow(
            "broadcast-goal-preparation",
            {
                "file_name": "scene.blend",
                "object_name": "Goal_Left_post",
                "target_location": [0.0, 5.302],
                "target_rotation": [0.0, 0.0, 15.0],
            },
        )


def test_catalog_builder_accepts_explicit_supported_version():
    template = build_soccer_production_workflow(
        "broadcast-goal-preparation",
        {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "target_location": [1.0, 2.0, 3.0],
            "target_rotation": [0.0, 0.0, 15.0],
        },
        version=1,
    )

    assert template.name == "broadcast-goal-preparation"
