import pytest

from controller.communication_gateway import CommunicationProtocolError
from controller.session_runtime import SessionControllerRuntime


def test_session_runtime_composes_open_command_replay_and_close():
    calls = []

    def handle_command(session_id, request_id, payload):
        calls.append((session_id, request_id, payload))
        return {"accepted": True, "command": payload["command"]}

    runtime = SessionControllerRuntime(handle_command)

    opened = runtime.open("atlas-session")
    assert opened["status"] == "ok"
    assert opened["event"] == "session_opened"
    assert opened["session_id"] == "atlas-session"

    first = runtime.command("atlas-session", "req-1", "inspect_scene", {"file_name": "scene.blend"})
    replay = runtime.command("atlas-session", "req-1", "inspect_scene", {"file_name": "scene.blend"})

    assert first == replay
    assert calls == [
        (
            "atlas-session",
            "req-1",
            {"command": "inspect_scene", "arguments": {"file_name": "scene.blend"}},
        )
    ]

    closed = runtime.close("atlas-session", "req-close")
    assert closed["status"] == "ok"
    assert closed["payload"]["event"] == "session_closed"

    with pytest.raises(CommunicationProtocolError, match="session is closed"):
        runtime.command("atlas-session", "req-2", "inspect_scene", {"file_name": "scene.blend"})


def test_session_runtime_rejects_invalid_session_ids_before_transport():
    runtime = SessionControllerRuntime(lambda *_: {"ok": True})

    with pytest.raises(ValueError, match="session_id must be a non-empty string"):
        runtime.open("")

    with pytest.raises(ValueError, match="session_id must be a non-empty string"):
        runtime.open(None)
