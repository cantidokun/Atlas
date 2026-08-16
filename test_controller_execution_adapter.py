"""Controller integration adapter tests."""

from controller_execution_adapter import ControllerExecutionAdapter


def test_adapter_inactive_for_unrelated_task():
    adapter = ControllerExecutionAdapter(
        "goalpost_test.blend",
        "Inspect the scene and report the objects.",
        [],
    )
    assert adapter.active is False


def test_adapter_activates_for_authorized_midpoint_task():
    ledger = [
        {
            "tool": "inspect_object_relationship",
            "arguments": {},
            "result": {
                "midpoint": [0.0, 0.138, 0.0],
                "object_a": {"name": "Goal_Left_post", "location": [0.0, 5.44, 0.0]},
                "object_b": {"name": "Goal_Right_Post", "location": [0.0, -5.164, 0.0]},
            },
        }
    ]
    task = (
        "The midpoint must be exactly [0.0, 0.0, 0.0]. "
        "You are explicitly authorized to modify the Blender file."
    )

    adapter = ControllerExecutionAdapter("goalpost_test.blend", task, ledger)

    assert adapter.active is True
    assert adapter.should_override_model_tool() is True


def test_adapter_records_controller_owned_write():
    ledger = [
        {
            "tool": "inspect_object_relationship",
            "arguments": {},
            "result": {
                "midpoint": [0.0, 0.138, 0.0],
                "object_a": {"name": "Goal_Left_post", "location": [0.0, 5.44, 0.0]},
                "object_b": {"name": "Goal_Right_Post", "location": [0.0, -5.164, 0.0]},
            },
        }
    ]
    task = (
        "The midpoint must be exactly [0.0, 0.0, 0.0]. "
        "You are explicitly authorized to modify the Blender file."
    )
    adapter = ControllerExecutionAdapter("goalpost_test.blend", task, ledger)
    history = []

    def execute(tool_name, arguments):
        assert tool_name == "move_object"
        return {
            "status": "moved",
            "object_name": arguments["object_name"],
            "location": arguments["location"],
        }

    result = adapter.execute_required_step(execute, history)

    assert result["status"] == "progress"
    assert result["phase"] == "WRITE"
    assert history[-1]["controller_owned"] is True
    assert ledger[-1]["controller_owned"] is True
    assert ledger[-1]["result"]["status"] == "moved"
