from controller.communication_loop import AutonomousCommunicationLoop
from controller.communication_runtime import ControllerCommunicationRuntime


def _start(runtime):
    runtime.handle_command(
        "session-1",
        "start-1",
        {
            "command": "start_task",
            "arguments": {"file_name": "fixture.blend", "task_text": "inspect"},
        },
    )


def test_autonomous_loop_retains_output_and_continues_without_human_relay():
    calls = []

    def model_executor(message, timeout_seconds):
        calls.append((message, timeout_seconds))
        return {
            "returncode": 0,
            "stdout": f"model-result:{len(calls)}",
            "stderr": "",
            "timed_out": False,
        }

    runtime = ControllerCommunicationRuntime(lambda tool, arguments: {"status": "ok"}, model_executor=model_executor)
    _start(runtime)
    loop = AutonomousCommunicationLoop(runtime, "session-1", model_executor=model_executor)

    first = loop.run_turn("turn-1", "Inspect the current controller state.", 10)
    second = loop.continue_from_last_turn("turn-2", "Now continue with the next development step.", 10)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert len(loop.turns) == 2
    assert loop.turns[0].response == "model-result:1"
    assert "model-result:1" in loop.turns[1].prompt
    assert calls[0] == ("Inspect the current controller state.", 10.0)
    assert "Next instruction:\nNow continue with the next development step." in calls[1][0]


def test_autonomous_loop_records_timeout_as_terminal():
    def model_executor(message, timeout_seconds):
        return {
            "returncode": -15,
            "stdout": "partial",
            "stderr": "",
            "timed_out": True,
        }

    runtime = ControllerCommunicationRuntime(lambda tool, arguments: {"status": "ok"}, model_executor=model_executor)
    _start(runtime)
    loop = AutonomousCommunicationLoop(runtime, "session-1", model_executor=model_executor)

    result = loop.run_turn("turn-1", "Continue.", 5)

    assert result["status"] == "timed_out"
    assert loop.terminal() is True
    assert loop.turns[0].response == "partial"
