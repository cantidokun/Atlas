from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_executor import BlenderToolExecutor


class FakeToolAdapter:
    def __init__(self):
        self.calls = []

    def inspect_scene(self, **arguments):
        self.calls.append(("inspect_scene", arguments))
        return {"status": "ok", "scene": "Test"}


def test_execution_boundary_can_use_explicit_tool_executor():
    adapter = FakeToolAdapter()
    executor = BlenderToolExecutor(handlers={"inspect_scene": adapter.inspect_scene})
    boundary = BlenderExecutionBoundary(executor.execute)

    result = boundary.execute("inspect_scene", {"file_name": "scene.blend"})

    assert result == {"status": "ok", "scene": "Test"}
    assert adapter.calls == [("inspect_scene", {"file_name": "scene.blend"})]
