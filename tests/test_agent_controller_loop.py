
"""Tests for the agent-loop controller adapter."""

import pytest

import controller.agent_controller_loop as loop


def _runtime():
    return loop.AtlasAgentEntrypointRuntime.__new__(
        loop.AtlasAgentEntrypointRuntime
    )


def test_adapter_requires_entrypoint_runtime():
    with pytest.raises(
        TypeError,
        match="AtlasAgentEntrypointRuntime",
    ):
        loop.AgentControllerLoopAdapter(object())


def test_normal_model_response_is_delegated_as_no_op(monkeypatch):
    calls = []

    def fake_bridge(*args, **kwargs):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr(
        loop,
        "submit_controller_request_from_model_output",
        fake_bridge,
    )

    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    result = adapter.process_model_response(
        "Continue ordinary Blender reasoning."
    )

    assert result is None
    assert len(calls) == 1
    assert calls[0][0][0] is runtime
    assert calls[0][0][1] == "Continue ordinary Blender reasoning."


def test_controller_response_is_delegated(monkeypatch):
    captured = {}

    def fake_bridge(runtime, content, **kwargs):
        captured["runtime"] = runtime
        captured["content"] = content
        captured["kwargs"] = kwargs
        return "controller-result"

    monkeypatch.setattr(
        loop,
        "submit_controller_request_from_model_output",
        fake_bridge,
    )

    trusted_provider = lambda intent: {
        "trusted": True,
    }

    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(
        runtime,
        trusted_context_provider=trusted_provider,
    )

    model_response = (
        "ATLAS_CONTROLLER_REQUEST: "
        + '{"capability": "production"}'
    )

    result = adapter.process_model_response(model_response)

    assert result == "controller-result"
    assert captured["runtime"] is runtime
    assert captured["content"] == model_response
    assert captured["kwargs"]["trusted_context_provider"] is trusted_provider


def test_runtime_property_exposes_execution_runtime():
    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    assert adapter.runtime is runtime


def test_trusted_provider_is_optional(monkeypatch):
    captured = {}

    def fake_bridge(runtime, content, **kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(
        loop,
        "submit_controller_request_from_model_output",
        fake_bridge,
    )

    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    adapter.process_model_response(
        "No controller request here."
    )

    assert captured["trusted_context_provider"] is None
