"""Tests for the host-owned agent controller lifecycle."""

import pytest

from controller.agent_controller_host import AgentControllerHost
from controller.agent_controller_intent import AgentControllerIntent
from controller.agent_execution_context import AgentExecutionContext
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.agent_trusted_context import AgentTrustedContext
from controller.trusted_unreal_context import TrustedUnrealContext
from controller.capability_request import CapabilityRequest
from planning.unreal_production_controller_integration import (
    UnrealProductionControllerIntegration,
)


def _runtime():
    return AtlasAgentEntrypointRuntime()


def _trusted_unreal_context():
    from tests.test_trusted_unreal_context import _authorized, _intent

    intent = _intent("host-lifecycle")
    authorized = _authorized(intent.intent_id)

    return TrustedUnrealContext(
        authorized_production=authorized,
        intent=intent,
        sequence_asset_path="/Game/Trusted/Sequence",
    )


def test_host_creates_isolated_runtime_and_execution_context():
    host = AgentControllerHost()

    assert isinstance(host.runtime, AtlasAgentEntrypointRuntime)
    assert isinstance(host.process, AtlasAgentProcessRuntime)
    assert isinstance(host.execution_context, AgentExecutionContext)
    assert host.loop.runtime is host.runtime
    assert host.execution_context.has("unreal") is False


def test_host_accepts_existing_dependencies():
    runtime = _runtime()
    context = AgentExecutionContext()

    host = AgentControllerHost(
        runtime=runtime,
        execution_context=context,
    )

    assert host.runtime is runtime
    assert host.process is runtime.process
    assert host.execution_context is context


def test_host_rejects_wrong_dependency_types():
    with pytest.raises(
        TypeError,
        match="AtlasAgentEntrypointRuntime",
    ):
        AgentControllerHost(runtime=object())

    with pytest.raises(
        TypeError,
        match="AtlasAgentProcessRuntime",
    ):
        AgentControllerHost(process=object())

    with pytest.raises(
        TypeError,
        match="AgentExecutionContext",
    ):
        AgentControllerHost(execution_context=object())


def test_host_installs_trusted_unreal_context():
    host = AgentControllerHost()
    trusted = _trusted_unreal_context()

    host.install_unreal_context(trusted)

    exported = host.execution_context.context_for_request("unreal")

    assert exported["authorized_production"] is trusted.authorized_production
    assert exported["intent"] is trusted.intent
    assert exported["sequence_asset_path"] == "/Game/Trusted/Sequence"


def test_host_routes_provider_from_model_intent_to_installed_context():
    host = AgentControllerHost()
    trusted = AgentTrustedContext.from_values({"approved": True})
    host.execution_context.install("unreal", trusted)

    captured = {}

    def fake_process(content):
        captured["content"] = content
        return None

    host.loop.process_model_response = fake_process
    result = host.process_model_response("ATLAS_CONTROLLER_REQUEST: {}")

    assert result is None
    assert captured["content"] == "ATLAS_CONTROLLER_REQUEST: {}"


def test_execution_context_provider_binding_does_not_use_model_context():
    host = AgentControllerHost()
    trusted = AgentTrustedContext.from_values({"approved": True})
    host.execution_context.install("unreal", trusted)

    from controller.agent_controller_response_bridge import (
        submit_controller_request_from_model_output,
    )

    request = (
        'ATLAS_CONTROLLER_REQUEST: '
        '{"capability":"production","provider":"unreal",'
        '"context":{"approved":false,"forged":"model"}}'
    )

    result = submit_controller_request_from_model_output(
        host.runtime,
        request,
        trusted_context_provider=host.execution_context.context_for_controller_intent,
    )

    assert result is not None
    assert result.controller_executed is False


def test_unreal_production_factory_binds_real_integration_and_trusted_context():
    integration = object.__new__(UnrealProductionControllerIntegration)
    trusted = _trusted_unreal_context()

    host = AgentControllerHost.for_unreal_production(
        integration,
        trusted,
    )

    assert host.process is host.runtime.process
    assert host.process.runtime is not None
    assert host.execution_context.get("unreal") is not None
    assert (
        host.execution_context.get("unreal").get("authorized_production")
        is trusted.authorized_production
    )


def test_unreal_production_factory_requires_typed_dependencies():
    trusted = _trusted_unreal_context()

    with pytest.raises(
        TypeError,
        match="UnrealProductionControllerIntegration",
    ):
        AgentControllerHost.for_unreal_production(object(), trusted)

    integration = object.__new__(UnrealProductionControllerIntegration)

    with pytest.raises(
        TypeError,
        match="TrustedUnrealContext",
    ):
        AgentControllerHost.for_unreal_production(integration, object())


def test_host_factory_routes_real_model_request_to_registered_unreal_integration(monkeypatch):
    integration = object.__new__(UnrealProductionControllerIntegration)
    trusted = _trusted_unreal_context()
    captured = {}

    def fake_execute(request: CapabilityRequest):
        captured["request"] = request
        return {"status": "accepted"}

    monkeypatch.setattr(integration, "execute", fake_execute)

    host = AgentControllerHost.for_unreal_production(
        integration,
        trusted,
    )

    model_response = (
        "ATLAS_CONTROLLER_REQUEST: "
        '{"capability":"production","provider":"unreal",'
        '"context":{"production":true,"authorized_production":"forged",'
        '"intent":"forged","sequence_asset_path":"/Game/Forged"},'
        '"intent":"forged-model-intent"}'
    )

    result = host.process_model_response(model_response)

    assert result is not None
    assert result.controller_executed is True
    assert captured["request"].provider == "unreal"
    assert captured["request"].capability == "production"
    assert captured["request"].context["production"] is True
    assert (
        captured["request"].context["authorized_production"]
        is trusted.authorized_production
    )
    assert captured["request"].context["intent"] is trusted.intent
    assert (
        captured["request"].context["sequence_asset_path"]
        == trusted.sequence_asset_path
    )
    assert result.classified.request.intent == "forged-model-intent"
