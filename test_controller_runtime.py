from controller_runtime import ControllerRuntime


BEFORE = {
    "object_a": {
        "name": "Goal_Left_post",
        "location": [0.0, 5.44, 0.0],
    },
    "object_b": {
        "name": "Goal_Right_Post",
        "location": [0.0, -5.164, 0.0],
    },
    "midpoint": [0.0, 0.138, 0.0],
}


def test_runtime_forces_both_writes_before_verification():
    runtime = ControllerRuntime("goalpost_test.blend")
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))

        if tool == "inspect_object_relationship":
            if len(calls) == 1:
                return BEFORE
            return {
                "object_a": {
                    "name": "Goal_Left_post",
                    "location": [0.0, 5.302, 0.0],
                },
                "object_b": {
                    "name": "Goal_Right_Post",
                    "location": [0.0, -5.302, 0.0],
                },
                "midpoint": [0.0, 0.0, 0.0],
            }

        if tool == "move_object":
            return {
                "status": "moved",
                "object_name": arguments["object_name"],
                "location": arguments["location"],
            }

        raise AssertionError(tool)

    first = runtime.step(execute)
    assert first["phase"] == "TARGET"
    assert first["next_action"]["kind"] == "write"

    second = runtime.step(execute)
    assert second["phase"] == "WRITE"
    assert second["next_action"]["kind"] == "write"
    assert calls[1][1]["object_name"] == "Goal_Left_post"

    third = runtime.step(execute)
    assert third["phase"] == "WRITE"
    assert third["next_action"]["kind"] == "verification"
    assert calls[2][1]["object_name"] == "Goal_Right_Post"

    fourth = runtime.step(execute)
    assert fourth["status"] == "complete"
    assert fourth["phase"] == "AFTER"
    assert runtime.state.phase == "AFTER"
    assert runtime.state.complete is True
    assert runtime._next_action()["kind"] == "complete"


def test_failed_write_does_not_advance_controller():
    runtime = ControllerRuntime("goalpost_test.blend")
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "inspect_object_relationship":
            return BEFORE
        return {"status": "error", "error": "write failed"}

    runtime.step(execute)
    result = runtime.step(execute)

    assert result["status"] == "error"
    assert runtime.state.writes == []
    assert runtime.state.phase == "TARGET"
    assert runtime._next_action()["kind"] == "write"
