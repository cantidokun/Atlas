
"""Tests for the agent-loop controller adapter."""

import pytest

import controller.agent_controller_loop as loop
from controller.agent_controller_intent import AgentControllerIntent
from controller.agent_execution_context import AgentExecutionContext
from controller.agent_trusted_context import AgentTrustedContext


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

    trusted_provider = lambda intent: AgentTrustedContext.from_values(
        {"trusted": True}
    )

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
    assert adapter.execution_context is None


def test_runtime_property_exposes_execution_runtime():
    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    assert adapter.runtime is runtime


def test_default_adapter_owns_empty_execution_context(monkeypatch):
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

    assert isinstance(adapter.execution_context, AgentExecutionContext)
    assert adapter.execution_context.has("unreal") is False
    assert callable(captured["trusted_context_provider"])

    intent = AgentControllerIntent(
        capability="production",
        provider="unreal",
        context={"approved": True},
        intent="model-request",
    )

    assert (
        captured["trusted_context_provider"](intent).to_request_context()
        == {}
    )


def test_trusted_provider_is_optional_when_explicitly_supplied(monkeypatch):
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
    trusted_provider = lambda intent: AgentTrustedContext.empty()
    adapter = loop.AgentControllerLoopAdapter(
        runtime,
        trusted_context_provider=trusted_provider,
    )

    adapter.process_model_response(
        "No controller request here."
    )

    assert captured["trusted_context_provider"] is trusted_provider


def test_controller_marker_is_not_reinterpreted_as_a_blender_tool(monkeypatch):
    captured = {}

    def fake_bridge(runtime, content, **kwargs):
        captured["content"] = content
        return "controller-execution"

    monkeypatch.setattr(
        loop,
        "submit_controller_request_from_model_output",
        fake_bridge,
    )

    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    content = (
        "ATLAS_CONTROLLER_REQUEST: "
        + '{"capability": "production", "provider": "unreal"}'
    )

    result = adapter.process_model_response(content)

    assert result == "controller-execution"
    assert captured["content"] == content


def test_controller_adapter_does_not_supply_authorization_itself(monkeypatch):
    captured = {}

    def fake_bridge(runtime, content, **kwargs):
        captured.update(kwargs)
        return "execution"

    monkeypatch.setattr(
        loop,
        "submit_controller_request_from_model_output",
        fake_bridge,
    )

    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    adapter.process_model_response(
        "ATLAS_CONTROLLER_REQUEST: "
        + '{"capability": "production", "provider": "unreal"}'
    )

    assert isinstance(
        captured["trusted_context_provider"],
        type(loop.AgentControllerLoopAdapter(runtime). _trusted_context_provider),
    )


def test_adapter_can_use_host_execution_context(monkeypatch):
    captured = {}

    def fake_bridge(runtime, content, **kwargs):
        captured["provider"] = kwargs["trusted_context_provider"]
        return None

    monkeypatch.setattr(
        loop,
        "submit_controller_request_from_model_output",
        fake_bridge,
    )

    execution_context = AgentExecutionContext()
    execution_context.install(
        "unreal",
        AgentTrustedContext.from_values(
            {
                "approved": True,
            }
        ),
    )

    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(
        runtime,
        execution_context=execution_context,
    )

    adapter.process_model_response(
        "No controller request here."
    )

    provider = captured["provider"]
    intent = AgentControllerIntent(
        capability="production",
        provider="unreal",
        context={},
        intent="requested-production",
    )

    trusted = provider(intent)

    assert trusted.get("approved") is True


def test_adapter_can_install_typed_trusted_context_into_owned_context():
    runtime = _runtime()
    adapter = loop.AgentControllerLoopAdapter(runtime)

    trusted = AgentTrustedContext.from_values(
        {
            "approved": True,
        }
    )

    adapter.install_trusted_context("unreal", trusted)

    assert adapter.execution_context.get("unreal") is trusted


def test_adapter_rejects_two_trusted_context_sources():
    runtime = _runtime()

    with pytest.raises(
        ValueError,
        match="or execution_context",
    ):
        loop.AgentControllerLoopAdapter(
            runtime,
            trusted_context_provider=lambda intent: AgentTrustedContext.empty(),
            execution_context=AgentExecutionContext(),
        )
