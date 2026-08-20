"""Focused coverage for the composed local controller communication host."""

import io
import json

from controller.communication_stdio import run_controller_stdio


TASK = (
    "Move the midpoint to [0.0, 0.0, 0.0]. "
    "The user is authorized to modify the scene."
)


def test_run_controller_stdio_wires_transport_gateway_and_runtime():
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return {"status": "ok"}

    stdin = io.StringIO("\n".join([
        json.dumps({
            "protocol_version": "1",
            "type": "open",
            "id": "open-1",
            "payload": {"session_id": "session-1"},
        }),
        json.dumps({
            "protocol_version": "1",
            "type": "command",
            "id": "start-1",
            "session_id": "session-1",
            "payload": {
                "command": "start_task",
                "arguments": {"file_name": "fixture.blend", "task_text": TASK},
            },
        }),
    ]) + "\n")
    stdout = io.StringIO()

    run_controller_stdio(execute, stdin, stdout)
    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]

    assert responses[0]["event"] == "session_opened"
    assert responses[1]["payload"]["status"] == "started"
    assert responses[1]["payload"]["controller_active"] is True
    assert responses[1]["payload"]["next_action"]["controller_owned"] is True
    assert calls == []
