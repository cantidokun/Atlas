from controller.controller_runtime import ControllerRuntime


def test_tool_exception_does_not_mutate_controller_state():
    runtime = ControllerRuntime("scene.blend")
    before = runtime.state.__dict__.copy()

    result = runtime.step(lambda *_: (_ for _ in ()).throw(RuntimeError("Blender unavailable")))

    assert result["status"] == "error"
    assert result["error"]["type"] == "RuntimeError"
    assert runtime.state.__dict__ == before


def test_non_object_result_does_not_advance_state():
    runtime = ControllerRuntime("scene.blend")
    result = runtime.step(lambda *_: ["bad"])

    assert result["status"] == "error"
    assert result["error"]["type"] == "InvalidToolResult"
    assert runtime.state.phase == "EMPTY"


def test_failure_status_does_not_advance_state():
    runtime = ControllerRuntime("scene.blend")
    result = runtime.step(lambda *_: {"status": "failed", "error": "write failed"})

    assert result["status"] == "error"
    assert runtime.state.phase == "EMPTY"
