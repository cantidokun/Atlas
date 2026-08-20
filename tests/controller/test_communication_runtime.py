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


def start_session(runtime):
    runtime.handle_command(
        "session-1",
        "start-1",
        {
            "command": "start_task",
            "arguments": {"file_name": "fixture.blend", "task_text": TASK},
        },
    )


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


def test_model_run_completes_a_bounded_local_turn_and_returns_output():
    calls = []

    def model_executor(message, timeout_seconds):
        calls.append((message, timeout_seconds))
        return {
            "returncode": 0,
            "stdout": "Aider completed the requested inspection.",
            "stderr": "",
            "timed_out": False,
        }

    runtime = ControllerCommunicationRuntime(make_runtime(calls)._execute_tool, model_executor=model_executor)
    start_session(runtime)

    result = runtime.handle_command(
        "session-1",
        "model-run-1",
        {
            "command": "model_run",
            "arguments": {
                "turn_id": "turn-1",
                "message": "Inspect the controller boundary.",
                "timeout_seconds": 30,
            },
        },
    )

    assert result["status"] == "completed"
    assert result["model_turn"]["state"] == "completed"
    assert result["result"]["stdout"] == "Aider completed the requested inspection."
    assert calls == [("Inspect the controller boundary.", 30.0)]


def test_model_run_maps_provider_timeout_to_timed_out_without_retry():
    calls = []

    def model_executor(message, timeout_seconds):
        calls.append((message, timeout_seconds))
        return {
            "returncode": -15,
            "stdout": "partial",
            "stderr": "",
            "timed_out": True,
        }

    runtime = ControllerCommunicationRuntime(make_runtime(calls)._execute_tool, model_executor=model_executor)
    start_session(runtime)

    result = runtime.handle_command(
        "session-1",
        "model-run-1",
        {
            "command": "model_run",
            "arguments": {
                "turn_id": "turn-1",
                "message": "Continue the task.",
                "timeout_seconds": 5,
            },
        },
    )

    assert result["status"] == "timed_out"
    assert result["model_turn"]["expired"] is True
    assert calls == [("Continue the task.", 5.0)]


def test_model_run_maps_nonzero_provider_exit_to_failed_without_retry():
    def model_executor(message, timeout_seconds):
        return {
            "returncode": 2,
            "stdout": "",
            "stderr": "aider failed",
            "timed_out": False,
        }

    runtime = ControllerCommunicationRuntime(make_runtime([])._execute_tool, model_executor=model_executor)
    start_session(runtime)

    result = runtime.handle_command(
        "session-1",
        "model-run-1",
        {
            "command": "model_run",
            "arguments": {
                "turn_id": "turn-1",
                "message": "Continue the task.",
                "timeout_seconds": 5,
            },
        },
    )

    assert result["status"] == "failed"
    assert result["model_turn"]["error"] == "aider failed"


def test_model_run_provider_exception_fails_closed():
    def model_executor(message, timeout_seconds):
        raise RuntimeError("provider unavailable")

    runtime = ControllerCommunicationRuntime(make_runtime([])._execute_tool, model_executor=model_executor)
    start_session(runtime)

    result = runtime.handle_command(
        "session-1",
        "model-run-1",
        {
            "command": "model_run",
            "arguments": {
                "turn_id": "turn-1",
                "message": "Continue the task.",
                "timeout_seconds": 5,
            },
        },
    )

    assert result["status"] == "failed"
    assert "provider unavailable" in result["model_turn"]["error"]
