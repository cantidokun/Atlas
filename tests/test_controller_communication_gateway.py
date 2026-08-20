import io
import json

from controller.communication_gateway import (
    CommunicationProtocolError,
    ControllerCommunicationGateway,
)
from controller.communication_stdio import process_lines


def test_command_executes_once_and_duplicate_request_id_replays_response():
    calls = []

    def handle_command(session_id, request_id, command):
        calls.append((session_id, request_id, command))
        return {"accepted": True, "command": command["command"]}

    gateway = ControllerCommunicationGateway(handle_command)

    opened = gateway.handle_message({
        "protocol_version": "1",
        "id": "open-1",
        "type": "open",
        "payload": {"session_id": "session-1"},
    })
    assert opened["status"] == "ok"

    request = {
        "protocol_version": "1",
        "id": "command-1",
        "type": "command",
        "session_id": "session-1",
        "payload": {"command": "inspect", "arguments": {"target": "scene"}},
    }

    first = gateway.handle_message(request)
    second = gateway.handle_message(request)

    assert first == second
    assert len(calls) == 1


def test_request_id_reuse_with_changed_payload_fails_closed():
    gateway = ControllerCommunicationGateway(lambda *_: {"accepted": True})
    gateway.handle_message({
        "protocol_version": "1",
        "id": "open-1",
        "type": "open",
        "payload": {"session_id": "session-1"},
    })

    request = {
        "protocol_version": "1",
        "id": "command-1",
        "type": "command",
        "session_id": "session-1",
        "payload": {"command": "inspect", "arguments": {}},
    }
    gateway.handle_message(request)

    request["payload"] = {"command": "write", "arguments": {"target": "scene"}}

    try:
        gateway.handle_message(request)
    except CommunicationProtocolError as exc:
        assert "reused" in str(exc)
    else:
        raise AssertionError("request_id reuse must fail closed")


def test_stdio_protocol_error_never_reaches_command_handler():
    calls = []

    def handle_command(*args):
        calls.append(args)
        raise AssertionError("command handler must not run")

    gateway = ControllerCommunicationGateway(handle_command)
    output = io.StringIO()

    process_lines(gateway, ["not-json\n"], output)

    response = json.loads(output.getvalue())
    assert response["status"] == "error"
    assert response["error"]["code"] == "protocol_error"
    assert calls == []


def test_closed_session_rejects_future_commands():
    gateway = ControllerCommunicationGateway(lambda *_: {"accepted": True})
    gateway.handle_message({
        "protocol_version": "1",
        "id": "open-1",
        "type": "open",
        "payload": {"session_id": "session-1"},
    })
    gateway.handle_message({
        "protocol_version": "1",
        "id": "close-1",
        "type": "close",
        "session_id": "session-1",
    })

    try:
        gateway.handle_message({
            "protocol_version": "1",
            "id": "command-1",
            "type": "command",
            "session_id": "session-1",
            "payload": {"command": "inspect", "arguments": {}},
        })
    except CommunicationProtocolError as exc:
        assert "closed" in str(exc)
    else:
        raise AssertionError("closed session must reject commands")
