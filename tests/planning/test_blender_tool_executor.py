import pytest

from planning.blender_tool_executor import BlenderToolExecutor, BlenderToolExecutorError


class FakeBlender:
    def __init__(self):
        self.calls = []

    def inspect_scene(self, **arguments):
        self.calls.append(("inspect_scene", arguments))
        return {"status": "ok"}

    def move_object(self, **arguments):
        self.calls.append(("move_object", arguments))
        return {"status": "moved"}


def test_executor_dispatches_only_explicit_handlers():
    fake = FakeBlender()
    executor = BlenderToolExecutor(
        handlers={
            "inspect_scene": fake.inspect_scene,
            "move_object": fake.move_object,
        }
    )

    result = executor.execute("inspect_scene", {"file_name": "scene.blend"})

    assert result == {
        "ok": True,
        "state": "completed",
        "details": {"status": "ok"},
    }
    assert fake.calls == [("inspect_scene", {"file_name": "scene.blend"})]


def test_unknown_tool_is_rejected_without_dynamic_lookup():
    executor = BlenderToolExecutor(handlers={})

    with pytest.raises(BlenderToolExecutorError, match="not executable"):
        executor.execute("execute_arbitrary_python", {"code": "print(1)"})


def test_non_object_arguments_are_rejected():
    executor = BlenderToolExecutor(handlers={})

    with pytest.raises(BlenderToolExecutorError, match="arguments must be an object"):
        executor.execute("inspect_scene", "not-an-object")


def test_handler_type_error_is_normalized():
    def handler(required):
        return {"status": "ok"}

    executor = BlenderToolExecutor(handlers={"test": handler})

    with pytest.raises(BlenderToolExecutorError, match="invalid invocation"):
        executor.execute("test", {})


def test_non_object_handler_result_is_rejected():
    executor = BlenderToolExecutor(handlers={"test": lambda **_: ["bad"]})

    with pytest.raises(BlenderToolExecutorError, match="non-object result"):
        executor.execute("test", {})
