from controller.controller_runtime import ControllerRuntime


def relationship(left=(-2.0, 0.0, 0.0), right=(2.0, 0.0, 0.0)):
    return {"object_a": {"name": "Goal_Left_post", "location": list(left)}, "object_b": {"name": "Goal_Right_Post", "location": list(right)}, "midpoint": [(left[i] + right[i]) / 2 for i in range(3)]}


def test_already_correct_scene_is_reverified_without_writes():
    runtime = ControllerRuntime("scene.blend")
    calls = []

    def execute(tool, args):
        calls.append((tool, args))
        if tool == "inspect_object_relationship":
            return relationship()
        raise AssertionError("No write should be required")

    result = runtime.step(execute)
    assert result["status"] == "progress"
    assert runtime.state.phase == "TARGET"
    assert calls[0][0] == "inspect_object_relationship"
    assert result["next_action"]["kind"] == "verification"


def test_failed_write_can_be_retried_without_consuming_the_step():
    runtime = ControllerRuntime("scene.blend")
    runtime.step(lambda *_: relationship(left=(8.0, 0.0, 0.0), right=(12.0, 0.0, 0.0)))

    result = runtime.step(lambda *_: {"status": "failed", "error": "temporary failure"})
    assert result["status"] == "error"
    assert runtime.state.phase == "TARGET"
    assert runtime.state.writes == []

    result = runtime.step(lambda *_: {"status": "moved"})
    assert result["status"] == "progress"
    assert len(runtime.state.writes) == 1
