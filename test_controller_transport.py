import io
import json

from controller_transport import process_lines
from controller_bridge import ControllerBridge


def test_process_lines_drives_bridge_and_flushes_response():
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))

        if tool == "inspect_object_relationship":
            return {
                "object_a": {"name": "Goal_Left_post", "location": [0.0, 5.302, 0.0]},
                "object_b": {"name": "Goal_Right_Post", "location": [0.0, -5.302, 0.0]},
                "midpoint": [0.0, 0.0, 0.0],
            }

        if tool == "move_object":
            return {
                "status": "moved",
                "object_name": arguments["object_name"],
                "location": arguments["location"],
            }

        raise AssertionError(tool)

    bridge = ControllerBridge(execute)
    message = {
        "protocol_version": "1",
        "id": "request-1",
        "type": "instruction",
        "payload": {"file_name": "goalpost_test.blend"},
    }
    output = io.StringIO()

    process_lines(bridge, [json.dumps(message) + "\n"], output)

    response = json.loads(output.getvalue())
    assert response["status"] == "complete"
    assert response["id"] == "request-1"
    assert [tool for tool, _ in calls] == [
        "inspect_object_relationship",
        "move_object",
        "move_object",
        "inspect_object_relationship",
    ]


def test_process_lines_returns_protocol_error_without_executing_tools():
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        raise AssertionError("executor must not be called")

    bridge = ControllerBridge(execute)
    output = io.StringIO()

    process_lines(bridge, ["not-json\n"], output)

    response = json.loads(output.getvalue())
    assert response["status"] == "error"
    assert response["error"]["code"] == "protocol_error"
    assert calls == []


def test_process_lines_can_close_transport_session():
    bridge = ControllerBridge(lambda tool, arguments: {})
    output = io.StringIO()

    process_lines(
        bridge,
        [json.dumps({"type": "close"}) + "\n"],
        output,
    )

    response = json.loads(output.getvalue())
    assert response["status"] == "complete"
    assert response["event"] == "session_closed"
    assert bridge.session.closed is True
