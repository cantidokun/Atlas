from controller_bridge import ControllerBridge, controller_required_for_midpoint_task


def test_midpoint_task_requires_controller_before_final_state():
    task = (
        "The midpoint must be exactly [0.0, 0.0, 0.0]. "
        "You are authorized to modify the Blender file."
    )

    assert controller_required_for_midpoint_task(task, []) is True


def test_midpoint_task_does_not_require_controller_after_verified_target():
    task = (
        "The midpoint must be exactly [0.0, 0.0, 0.0]. "
        "You are authorized to modify the Blender file."
    )
    ledger = [
        {
            "tool": "inspect_object_relationship",
            "arguments": {},
            "result": {"midpoint": [0.0, 0.0, 0.0]},
        }
    ]

    assert controller_required_for_midpoint_task(task, ledger) is False


def test_unrelated_task_does_not_activate_midpoint_controller():
    task = "Inspect the scene and report the render settings."
    assert controller_required_for_midpoint_task(task, []) is False


def test_bridge_exposes_controller_state():
    bridge = ControllerBridge("goalpost_test.blend")

    assert bridge.is_complete() is False
    assert bridge.next_action()["kind"] == "evidence"
