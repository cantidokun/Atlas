"""Final integration proof for the controller communication bridge."""

import os
import sys

from controller.communication_client import ControllerStdioClient


def test_complete_development_session_requires_no_human_bridge(tmp_path):
    """Drive two model turns through the real host without manual relay."""
    executor_module = tmp_path / "fake_executor.py"
    executor_module.write_text(
        "def execute(tool, arguments):\n"
        "    return {'status': 'ok', 'tool': tool, 'arguments': arguments}\n",
        encoding="utf-8",
    )

    # This process stands in for the installed Aider executable.  It behaves
    # like a model client from the controller's perspective while remaining
    # deterministic and offline for CI.
    fake_aider = tmp_path / "fake_aider.py"
    fake_aider.write_text(
        "import sys\n"
        "message = sys.argv[sys.argv.index('--message') + 1]\n"
        "if message.startswith('objective:'):\n"
        "    print('AIDER_RESULT:implemented:' + message.split(':', 1)[1])\n"
        "else:\n"
        "    print('AIDER_RESULT:verified:' + message)\n",
        encoding="utf-8",
    )

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    python_paths = [str(tmp_path), os.getcwd()]
    if existing_pythonpath:
        python_paths.append(existing_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)

    client = ControllerStdioClient.launch(
        [
            sys.executable,
            "-m",
            "controller.communication_host",
            "--working-directory",
            str(tmp_path),
            "--tool-executor",
            "fake_executor:execute",
            "--aider-executable",
            sys.executable,
            "--aider-arg",
            str(fake_aider),
            "--max-model-turn-seconds",
            "5",
        ],
        environment=environment,
    )

    try:
        # Everything after this point is machine-to-machine.  No response is
        # copied, reformatted, or approved by a human between requests.
        opened = client.open_session("autonomous-session-1")
        assert opened["session_id"] == "autonomous-session-1"

        started = client.command(
            "start_task",
            {
                "file_name": "fixture.blend",
                "task_text": "Implement and verify the requested controller change.",
            },
        )
        assert started["status"] == "started"

        first = client.command(
            "model_run",
            {
                "turn_id": "autonomous-turn-1",
                "message": "objective:create-controller-change",
                "timeout_seconds": 5,
            },
        )
        assert first["status"] == "completed"
        assert "AIDER_RESULT:implemented:create-controller-change" in first["result"]["stdout"]

        # The programmatic orchestrator consumes the first result and issues
        # the verification turn directly; this is the human-bridge boundary
        # the integration must eliminate.
        continuation = (
            "Verify the result of the previous turn. Previous result: "
            + first["result"]["stdout"].strip()
        )
        second = client.command(
            "model_run",
            {
                "turn_id": "autonomous-turn-2",
                "message": continuation,
                "timeout_seconds": 5,
            },
        )
        assert second["status"] == "completed"
        assert "AIDER_RESULT:verified:" in second["result"]["stdout"]

        status = client.command("status")
        assert status["model_turn"]["state"] == "completed"
        assert status["tool_execution_count"] == 0
    finally:
        client.close()
