from controller.controller_runtime import ControllerRuntime


def test_non_dict_tool_result_fails_closed():
    runtime = ControllerRuntime("scene.blend")
    result = runtime.step(lambda *_: None)
    assert result["status"] == "error"
    assert runtime.state.phase == "EMPTY"


def test_explicit_error_status_fails_closed():
    runtime = ControllerRuntime("scene.blend")
    result = runtime.step(lambda *_: {"status": "error", "error": "bad evidence"})
    assert result["status"] == "error"
    assert runtime.state.phase == "EMPTY"


def test_runtime_does_not_expose_mutable_next_action():
    runtime = ControllerRuntime("scene.blend")
    first = runtime._next_action()
    first["arguments"]["file_name"] = "tampered.blend"
    assert runtime._next_action()["arguments"]["file_name"] == "scene.blend"
