import json

import pytest

from qwen.ollama_provider import (
    DEFAULT_OLLAMA_URL,
    DEFAULT_QWEN_MODEL,
    OllamaQwenProvider,
    QwenProviderError,
)


class FakeResponse:
    def __init__(self, body, *, error=None):
        self.body = body
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def _payload():
    return {
        "workflow": "broadcast-goal-preparation",
        "version": 1,
        "parameters": {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "target_location": [0.25, 5.302, 0.0],
            "target_rotation": [0.0, 0.0, 15.0],
        },
    }


def test_defaults_target_local_ollama_and_qwen():
    assert DEFAULT_OLLAMA_URL == "http://localhost:11434/api/chat"
    assert DEFAULT_QWEN_MODEL == "qwen3:8b"


def test_propose_uses_structured_schema_and_exposes_no_tools():
    session = FakeSession(FakeResponse({"message": {"content": json.dumps(_payload())}}))
    provider = OllamaQwenProvider(session=session)

    proposal = provider.propose("Prepare this soccer goal for a broadcast shot.")

    assert proposal.workflow == "broadcast-goal-preparation"
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == DEFAULT_OLLAMA_URL
    request = kwargs["json"]
    assert request["model"] == DEFAULT_QWEN_MODEL
    assert request["stream"] is False
    assert request["options"] == {"temperature": 0}
    assert request["format"]["type"] == "object"
    assert request["format"]["additionalProperties"] is False
    assert "tools" not in request
    assert "executor" not in request
    assert "authorization" not in request


def test_context_is_sent_as_prompt_only():
    session = FakeSession(FakeResponse({"message": {"content": json.dumps(_payload())}}))
    provider = OllamaQwenProvider(session=session)

    provider.propose(
        "Prepare the soccer goal.",
        context="Verified file: scene.blend; object: Goal_Left_post",
    )

    request_messages = session.calls[0][1]["json"]["messages"]
    assert request_messages[-1]["role"] == "user"
    assert "Verified context:" in request_messages[-1]["content"]


def test_custom_messages_remain_role_content_only():
    session = FakeSession(FakeResponse({"message": {"content": json.dumps(_payload())}}))
    provider = OllamaQwenProvider(session=session)

    provider.propose(
        "Prepare the soccer goal.",
        messages=[{"role": "system", "content": "Use the Atlas proposal contract."}],
    )

    request_messages = session.calls[0][1]["json"]["messages"]
    assert request_messages[0]["content"] == "Use the Atlas proposal contract."
    assert request_messages[-1]["content"] == "Prepare the soccer goal."


def test_provider_rejects_invalid_messages_before_network_call():
    session = FakeSession(FakeResponse({"message": {"content": json.dumps(_payload())}}))
    provider = OllamaQwenProvider(session=session)

    with pytest.raises(ValueError, match="role and content strings"):
        provider.propose(
            "Prepare the soccer goal.",
            messages=[{"role": "user", "content": "ok", "tool": "move_object"}],
        )

    assert session.calls == []


def test_provider_rejects_invalid_model_output():
    session = FakeSession(FakeResponse({"message": {"content": "{bad"}}))
    provider = OllamaQwenProvider(session=session)

    with pytest.raises(QwenProviderError, match="invalid production proposal"):
        provider.propose("Prepare the soccer goal.")


def test_provider_rejects_missing_message():
    session = FakeSession(FakeResponse({}))
    provider = OllamaQwenProvider(session=session)

    with pytest.raises(QwenProviderError, match="missing a message object"):
        provider.propose("Prepare the soccer goal.")


def test_provider_rejects_malformed_message_content():
    session = FakeSession(FakeResponse({"message": {"content": 123}}))
    provider = OllamaQwenProvider(session=session)

    with pytest.raises(QwenProviderError, match="missing proposal content"):
        provider.propose("Prepare the soccer goal.")


def test_provider_rejects_execution_fields_in_model_output():
    payload = _payload()
    payload["executor"] = "blender"
    session = FakeSession(FakeResponse({"message": {"content": json.dumps(payload)}}))
    provider = OllamaQwenProvider(session=session)

    with pytest.raises(QwenProviderError, match="invalid production proposal"):
        provider.propose("Prepare the soccer goal.")


def test_provider_wraps_transport_failure():
    session = FakeSession(FakeResponse({}, error=RuntimeError("boom")))
    provider = OllamaQwenProvider(session=session)

    with pytest.raises(RuntimeError, match="boom"):
        provider.propose("Prepare the soccer goal.")
