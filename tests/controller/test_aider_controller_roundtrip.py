"""Subprocess-level proof of the local Aider/controller composition boundary."""

import io
import json
import sys

from controller.communication_stdio import run_aider_controller_stdio


def test_aider_controller_roundtrip_uses_a_real_subprocess_boundary(tmp_path):
    """Prove stdio -> controller -> Aider adapter -> subprocess -> response."""
    stdin = io.StringIO(
        "\n".join(
            [
                json.dumps(
                    {
                        "protocol_version": "1",
                        "type": "open",
                        "id": "open-1",
                        "payload": {"session_id": "session-1"},
                    }
                ),
                json.dumps(
                    {
                        "protocol_version": "1",
                        "type": "command",
                        "id": "start-1",
                        "session_id": "session-1",
                        "payload": {
                            "command": "start_task",
                            "arguments": {
                                "file_name": "fixture.blend",
                                "task_text": "inspect",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "protocol_version": "1",
                        "type": "command",
                        "id": "model-1",
                        "session_id": "session-1",
                        "payload": {
                            "command": "model_run",
                            "arguments": {
                                "turn_id": "turn-1",
                                "message": "roundtrip-check",
                                "timeout_seconds": 5,
                            },
                        },
                    }
                ),
            ]
        )
        + "\n"
    )
    stdout = io.StringIO()

    # Use the Python interpreter as a deterministic stand-in for the Aider
    # executable. This exercises the real subprocess boundary without making
    # CI depend on credentials, a network provider, or an installed Aider CLI.
    fake_aider = (
        "import sys; "
        "assert '--message' in sys.argv; "
        "print('AIDER_SUBPROCESS_OK:' + sys.argv[sys.argv.index('--message') + 1])"
    )

    run_aider_controller_stdio(
        lambda tool, arguments: {"status": "ok"},
        str(tmp_path),
        executable=sys.executable,
        extra_args=("-c", fake_aider),
        stdin=stdin,
        stdout=stdout,
        max_model_turn_seconds=5,
    )

    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]

    assert responses[0]["event"] == "session_opened"
    assert responses[1]["payload"]["status"] == "started"
    assert responses[2]["payload"]["status"] == "completed"
    assert responses[2]["payload"]["result"]["timed_out"] is False
    assert responses[2]["payload"]["result"]["returncode"] == 0
    assert responses[2]["payload"]["result"]["stdout"].strip() == (
        "AIDER_SUBPROCESS_OK:roundtrip-check"
    )
