from controller.session_runtime import SessionControllerRuntime


def test_session_runtime_open_command_close():
    calls = []

    def handle_command(session_id, request_id, command):
        calls.append((session_id, request_id, command))
        return {"accepted": True, "command": command["command"]}

    runtime = SessionControllerRuntime(handle_command)

    opened = runtime.open("session-1")
    assert opened["status"] == "ok"

    response = runtime.command(
        "session-1",
        "request-1",
        "inspect",
        {"target": "scene"},
    )
    assert response["status"] == "ok"
    assert response["payload"]["accepted"] is True

    closed = runtime.close("session-1")
    assert closed["status"] == "ok"
    assert len(calls) == 1


def test_session_runtime_preserves_gateway_idempotency():
    calls = []

    def handle_command(*args):
        calls.append(args)
        return {"accepted": True}

    runtime = SessionControllerRuntime(handle_command)
    runtime.open("session-2")

    first = runtime.command("session-2", "request-2", "inspect", {})
    second = runtime.command("session-2", "request-2", "inspect", {})

    assert first == second
    assert len(calls) == 1
