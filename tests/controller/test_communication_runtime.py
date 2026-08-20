"""Focused offline coverage for communication-to-controller integration."""

import io
import json

from controller.communication_gateway import ControllerCommunicationGateway
from controller.communication_runtime import ControllerCommunicationRuntime
from controller.communication_stdio import process_lines


TASK = (
    "Move the midpoint to [0.0, 0.0, 0.0]. "
    "The user is authorized to modify the scene."
)


def make_runtime(calls):
    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "inspect_object_relationship":
            return {
                "object_a": {"name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]},
                "object_b": {"name": "Goal_Right_Post", "location": [0.0, -5.233, 0.0]},
                "midpoint": [1.0, 0.0, 0.0],
            }
        if tool == "move_object":
            return {"status": "moved"}
        if tool == "inspect_object_relationship":
            return {"midpoint": [0.0, 0.0, 0.0]}
        return {"status": "ok"}

    return ControllerCommunicationRuntime(execute)


def open_gateway(runtime):
    return ControllerCommunicationGateway(runtime.handle_command)


def test_remote_command_reaches_existing_controller_without_arbitrary_tool_dispatch():
    calls = []
    gateway = open_gateway(make_runtime(calls))

    opened = gateway.handle_message({
        "protocol_version": "1",
        "type": "open",
        "id": "open-1",
        "payload": {"session_id": "session-1"},
    })
    assert opened["status"] == "ok"

    started = gateway.handle_message({
        "protocol_version": "1",
        "type": "command",
        "id": "start-1",
        "session_id": "session-1",
        "payload": {
            "command": "start_task",
            "arguments": {"file_name": "fixture.blend", "task_text": TASK},
        },
    })

    assert started["payload"]["controller_active"] is True
    assert started["payload"]["next_action"]["controller_owned"] is True

    next_response = gateway.handle_message({
        "protocol_version": "1",
        "type": "command",
        "id": "next-1",
        "session_id": "session-1",
        "payload": {"command": "next_action", "arguments": {}},
    })
    assert next_response["payload"]["status"] == "controller_action"
    assert next_response["payload"]["action"]["tool"] == "inspect_object_relationship"

    execute_message = {
        "protocol_version": "1",
        "type": "command",
        "id": "execute-1",
        "session_id": "session-1",
        "payload": {"command": "execute_next", "arguments": {}},
    }
    first = gateway.handle_message(execute_message)
    second = gateway.handle_message(execute_message)

    assert first == second
    assert len(calls) == 1
    assert calls[0][0] == "inspect_object_relationship"


def test_stdio_transport_can_complete_a_controller_command_round_trip():
    calls = []
    runtime = make_runtime(calls)
    gateway = open_gateway(runtime)
    output = io.StringIO()

    lines = [
        json.dumps({
            "protocol_version": "1",
            "type": "open",
            "id": "open-1",
            "payload": {"session_id": "session-1"},
        }),
        json.dumps({
            "protocol_version": "1",
            "type": "command",
            "id": "health-1",
            "session_id": "session-1",
            "payload": {"command": "health", "arguments": {}},
        }),
    ]

    process_lines(gateway, lines, output)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]

    assert responses[0]["event"] == "session_opened"
    assert responses[1]["payload"]["status"] == "ready"
    assert calls == []
