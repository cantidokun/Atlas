"""End-to-end offline proof of the machine-to-controller process boundary."""

import json
import os
import sys

from controller.communication_client import ControllerStdioClient


def test_client_reaches_controller_host_without_human_bridge(tmp_path):
    """Prove the programmatic client can drive the real host subprocess."""
    executor_module = tmp_path / "fake_executor.py"
    executor_module.write_text(
        "def execute(tool, arguments):\n"
        "    return {'status': 'ok', 'tool': tool}\n",
        encoding="utf-8",
    )

    fake_aider = tmp_path / "fake_aider.py"
    fake_aider.write_text(
        "import sys\n"
        "assert '--message' in sys.argv\n"
        "print('AIDER_PROCESS_OK:' + sys.argv[sys.argv.index('--message') + 1])\n",
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
        opened = client.open_session("session-process-1")
        started = client.command(
            "start_task",
            {"file_name": "fixture.blend", "task_text": "inspect"},
        )
        result = client.command(
            "model_run",
            {
                "turn_id": "turn-process-1",
                "message": "roundtrip-process-check",
                "timeout_seconds": 5,
            },
        )

        assert opened["session_id"] == "session-process-1"
        assert started["status"] == "started"
        assert result["status"] == "completed"
        assert result["result"]["returncode"] == 0
        assert result["result"]["timed_out"] is False
        assert "AIDER_PROCESS_OK:roundtrip-process-check" in result["result"]["stdout"]
    finally:
        client.close()


def test_client_survives_a_stalled_aider_turn_and_accepts_next_turn(tmp_path):
    """Prove a real stalled model process cannot permanently consume the bridge."""
    executor_module = tmp_path / "fake_executor.py"
    executor_module.write_text(
        "def execute(tool, arguments):\n"
        "    return {'status': 'ok', 'tool': tool}\n",
        encoding="utf-8",
    )

    fake_aider = tmp_path / "fake_aider.py"
    fake_aider.write_text(
        "import sys\n"
        "import time\n"
        "message = sys.argv[sys.argv.index('--message') + 1]\n"
        "if message == 'stall':\n"
        "    time.sleep(2)\n"
        "print('AIDER_PROCESS_OK:' + message)\n",
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
        client.open_session("session-stall-1")
        client.command(
            "start_task",
            {"file_name": "fixture.blend", "task_text": "inspect"},
        )

        stalled = client.command(
            "model_run",
            {
                "turn_id": "turn-stall-1",
                "message": "stall",
                "timeout_seconds": 0.1,
            },
        )

        assert stalled["status"] == "timed_out"
        assert stalled["model_turn"]["state"] == "timed_out"
        assert stalled["result"]["timed_out"] is True

        recovered = client.command(
            "model_run",
            {
                "turn_id": "turn-after-stall-1",
                "message": "recovered",
                "timeout_seconds": 5,
            },
        )

        assert recovered["status"] == "completed"
        assert recovered["model_turn"]["state"] == "completed"
        assert "AIDER_PROCESS_OK:recovered" in recovered["result"]["stdout"]
    finally:
        client.close()
