from controller.session_runtime import SessionControllerRuntime


def test_session_runtime_open_command_close_and_replay():
    calls = []

    def handle_command(session_id, request_id, command):
        calls.append((session_id, request_id, command))
        return {"accepted": True, "command": command["command"]}

    runtime = SessionControllerRuntime(handle_command)

    opened = runtime.open("session-1")
    assert opened["status"] == "ok"

    first = runtime.command("session-1", "request-1", "inspect", {"target": "scene"})
    replay = runtime.command("session-1", "request-1", "inspect", {"target": "scene"})
    assert first == replay
    assert len(calls) == 1

    closed = runtime.close("session-1", "close-1")
    assert closed["payload"]["event"] == "session_closed"
