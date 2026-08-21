from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep


def _steps():
    return [
        FutureStep(
            0,
            "action.0",
            "ACTION",
            "Execute authorized action.",
            {"tool": "move_object", "arguments": {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [0.25, 0.0, 0.0]}},
        ),
        FutureStep(1, "verification.pending", "VERIFICATION", "Verify."),
    ]


def test_unsuccessful_canonical_tool_result_blocks_controller():
    controller = FutureExecutionController(_steps())
    result = controller.execute_current(lambda *_: {"ok": False, "state": "failed", "details": {"error": "Object not found"}})

    assert result["ok"] is False
    assert controller.blocked is True
    assert controller.snapshot()["current_step"] is None
    assert controller.snapshot()["failure"]["step_id"] == "action.0"


def test_non_object_tool_result_blocks_controller():
    controller = FutureExecutionController(_steps())
    result = controller.execute_current(lambda *_: "not a result object")

    assert result["exception_type"] == "ToolResultTypeError"
    assert controller.blocked is True
