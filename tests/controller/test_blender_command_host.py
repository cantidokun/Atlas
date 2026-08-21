import pytest

from controller.blender_command_host import BlenderCommandHost
from planning.blender_tool_executor import BlenderToolExecutor


class FakeAdapter:
    def inspect_scene(self, **arguments):
        return {"status": "ok", "scene": "Test", "arguments": arguments}


def test_command_host_routes_through_verified_boundary():
    adapter = FakeAdapter()
    host = BlenderCommandHost(
        BlenderToolExecutor(handlers={"inspect_scene": adapter.inspect_scene})
    )

    result = host.handle("session-1", "request-1", {
        "command": "inspect_scene",
        "arguments": {"file_name": "scene.blend"},
    })

    assert result["session_id"] == "session-1"
    assert result["request_id"] == "request-1"
    assert result["tool"] == "inspect_scene"
    assert result["result"]["status"] == "ok"


def test_command_host_rejects_unapproved_tool():
    host = BlenderCommandHost(BlenderToolExecutor(handlers={}))

    with pytest.raises(ValueError):
        host.handle("session-1", "request-1", {
            "command": "execute_arbitrary_python",
            "arguments": {"code": "print(1)"},
        })
