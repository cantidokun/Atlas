"""Offline tests for bounded local-model communication."""

import requests
import pytest

from controller.autonomous_runtime import ModelTurn
from controller.model_gateway import ModelGatewayError, OllamaChatGateway


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, endpoint, json, timeout):
        self.calls.append((endpoint, json, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def test_gateway_passes_hard_timeout_to_http_client():
    session = FakeSession(
        response=FakeResponse({"message": {"content": "done", "tool_calls": []}})
    )
    gateway = OllamaChatGateway(
        "http://localhost:11434/api/chat",
        "deepseek",
        timeout_seconds=7.5,
        session=session,
    )

    result = gateway([{"role": "user", "content": "task"}])

    assert isinstance(result, ModelTurn)
    assert session.calls[0][2] == 7.5


def test_gateway_converts_model_timeout_to_controller_visible_error():
    session = FakeSession(error=requests.Timeout("stuck thinking"))
    gateway = OllamaChatGateway(
        "http://localhost:11434/api/chat",
        "deepseek",
        timeout_seconds=1.0,
        session=session,
    )

    with pytest.raises(ModelGatewayError, match="model_timeout"):
        gateway([{"role": "user", "content": "task"}])


def test_gateway_normalizes_one_tool_call():
    session = FakeSession(
        response=FakeResponse(
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "abc",
                            "function": {
                                "name": "inspect",
                                "arguments": {"target": "scene"},
                            },
                        }
                    ],
                }
            }
        )
    )
    gateway = OllamaChatGateway("http://localhost:11434/api/chat", "deepseek", session=session)

    result = gateway([])

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "inspect"
    assert result.tool_calls[0].arguments == {"target": "scene"}
