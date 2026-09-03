import pytest

from planning.soccer_production_catalog import (
    SoccerProductionWorkflowSpec,
    available_soccer_production_workflows,
    build_soccer_production_workflow,
    get_soccer_production_workflow,
    validate_soccer_production_workflow_parameters,
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


def test_catalog_validates_parameter_envelope_without_instantiating_template():
    spec = validate_soccer_production_workflow_parameters(
        "broadcast-goal-preparation",
        {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "target_location": [1.0, 2.0, 3.0],
            "target_rotation": [0.0, 0.0, 15.0],
        },
        version=1,
    )

    assert spec.name == "broadcast-goal-preparation"
    assert spec.version == 1

    with pytest.raises(TypeError, match="parameters must be a dictionary"):
        validate_soccer_production_workflow_parameters("broadcast-goal-preparation", [], version=1)

    with pytest.raises(ValueError, match="missing required parameters"):
        validate_soccer_production_workflow_parameters(
            "broadcast-goal-preparation",
            {"file_name": "scene.blend"},
            version=1,
        )


def test_catalog_builder_rejects_malformed_transform_containers_before_template_construction():
    with pytest.raises(TypeError, match="target_location must be a list or tuple"):
        build_soccer_production_workflow(
            "broadcast-goal-preparation",
            {
                "file_name": "scene.blend",
                "object_name": "Goal_Left_post",
                "target_location": "1,2,3",
                "target_rotation": [0.0, 0.0, 15.0],
            },
            version=1,
        )

    with pytest.raises(TypeError, match="target_rotation must be a list or tuple"):
        build_soccer_production_workflow(
            "broadcast-goal-preparation",
            {
                "file_name": "scene.blend",
                "object_name": "Goal_Left_post",
                "target_location": [0.0, 5.302, 0.0],
                "target_rotation": {"x": 0.0, "y": 0.0, "z": 15.0},
            },
            version=1,
        )
