from planning.soccer_production_catalog import compile_soccer_production_workflow


def _parameters():
    return {
        "file_name": "scene.blend",
        "object_name": "Goal_Left_post",
        "target_location": [0.25, 5.302, 0.0],
        "target_rotation": [0.0, 0.0, 15.0],
    }


def test_catalog_compilation_carries_exact_versioned_contract_into_task_metadata():
    task = compile_soccer_production_workflow(
        "broadcast-goal-preparation",
        _parameters(),
        version=1,
    )

    assert task.metadata["workflow_template"] == "broadcast-goal-preparation"
    assert task.metadata["workflow_catalog"] == {
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
    assert task.metadata["workflow_parameters"] == _parameters()


def test_catalog_compilation_normalizes_vector_parameters_without_mutating_input():
    parameters = _parameters()
    task = compile_soccer_production_workflow("broadcast-goal-preparation", parameters)

    assert task.metadata["workflow_parameters"] == parameters
    parameters["target_location"][0] = 99.0
    assert task.metadata["workflow_parameters"]["target_location"] == [0.25, 5.302, 0.0]


def test_catalog_compilation_resolves_explicit_version_and_preserves_single_task_contract():
    task = compile_soccer_production_workflow(
        "broadcast-goal-preparation",
        _parameters(),
        version=1,
    )

    assert task.name == "broadcast-goal-preparation"
    assert task.metadata["domain"] == "soccer-production"
    assert len(task.actions) == 2
    assert [action.name for action in task.actions] == ["position_goal", "orient_goal"]
