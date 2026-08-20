"""Focused coverage for gateway retry safety after handler failures."""

import pytest

from controller.communication_gateway import (
    CommunicationProtocolError,
    ControllerCommunicationGateway,
)


def _command(session_id="session-1", request_id="request-1", argument="value"):
    return {
        "protocol_version": "1",
        "type": "command",
        "id": request_id,
        "session_id": session_id,
        "payload": {
            "command": "mutate",
            "arguments": {"value": argument},
        },
    }


def test_handler_failure_is_terminal_for_the_request_id():
    calls = []

    def handler(session_id, request_id, payload):
        calls.append((session_id, request_id, payload))
        raise RuntimeError("executor failed after side effect")

    gateway = ControllerCommunicationGateway(handler)
    gateway.open_session("session-1")

    first = gateway.handle_message(_command())
    second = gateway.handle_message(_command())

    assert first == second
    assert first["status"] == "error"
    assert first["payload"]["error"]["code"] == "internal_error"
    assert first["payload"]["error"]["retryable"] is False
    assert len(calls) == 1


def test_failed_request_can_be_retried_with_a_new_request_id():
    calls = []

    def handler(session_id, request_id, payload):
        calls.append(request_id)
        raise RuntimeError("temporary local failure")

    gateway = ControllerCommunicationGateway(handler)
    gateway.open_session("session-1")

    first = gateway.handle_message(_command(request_id="request-1"))
    second = gateway.handle_message(_command(request_id="request-2"))

    assert first["status"] == "error"
    assert second["status"] == "error"
    assert calls == ["request-1", "request-2"]


def test_request_id_reuse_with_different_content_stays_a_protocol_error():
    calls = []

    def handler(session_id, request_id, payload):
        calls.append(payload)
        return {"status": "ok"}

    gateway = ControllerCommunicationGateway(handler)
    gateway.open_session("session-1")
    gateway.handle_message(_command(argument="first"))

    with pytest.raises(CommunicationProtocolError, match="request_id was reused"):
        gateway.handle_message(_command(argument="second"))

    assert len(calls) == 1
