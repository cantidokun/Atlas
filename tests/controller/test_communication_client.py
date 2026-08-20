"""Offline coverage for the machine-side controller communication client."""

import io

import pytest

from controller.communication_client import ControllerCommunicationError, ControllerStdioClient


class FakeStdin(io.StringIO):
    def __init__(self):
        super().__init__()
        self.lines = []

    def write(self, value):
        self.lines.append(value)
        return len(value)


class FakeStdout(io.StringIO):
    def __init__(self, responses):
        super().__init__("".join(response + "\n" for response in responses))


class FakeProcess:
    def __init__(self, responses):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(responses)
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_client_drives_open_command_and_close_without_human_message_copying():
    process = FakeProcess(
        [
            '{"protocol_version":"1","status":"ok","id":"client-1","session_id":"session-1","event":"session_opened"}',
            '{"protocol_version":"1","status":"ok","id":"client-2","session_id":"session-1","payload":{"status":"ready"}}',
            '{"protocol_version":"1","status":"ok","id":"client-3","session_id":"session-1","payload":{"event":"session_closed"}}',
        ]
    )
    client = ControllerStdioClient(process)

    opened = client.open_session("session-1")
    health = client.command("health")
    closed = client.close()

    assert opened["session_id"] == "session-1"
    assert health == {"status": "ready"}
    assert closed == {"event": "session_closed"}
    assert process.terminated is True
    assert len(process.stdin.lines) == 3
    assert '"type":"command"' in process.stdin.lines[1]
    assert '"command":"health"' in process.stdin.lines[1]


def test_client_rejects_command_before_session_open():
    process = FakeProcess([])
    client = ControllerStdioClient(process)

    with pytest.raises(ControllerCommunicationError, match="open_session"):
        client.command("health")


def test_client_fails_on_mismatched_response_id():
    process = FakeProcess(
        [
            '{"protocol_version":"1","status":"ok","id":"wrong","session_id":"session-1","event":"session_opened"}',
        ]
    )
    client = ControllerStdioClient(process)

    with pytest.raises(ControllerCommunicationError, match="response id"):
        client.open_session("session-1")
