"""Synthetic end-to-end coverage for the agent host to Unreal capability boundary."""

from controller.agent_controller_host import AgentControllerHost
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.agent_task_request import AgentTaskRequest
from controller.capability_request import CapabilityRequest
from controller.trusted_unreal_context import TrustedUnrealContext
from planning.unreal_production_controller_integration import (
    UnrealProductionControllerIntegration,
)


def _trusted_unreal_context():
    from tests.test_trusted_unreal_context import _authorized, _intent

    intent = _intent("synthetic-host-unreal")
    return TrustedUnrealContext(
        authorized_production=_authorized(intent.intent_id),
        intent=intent,
        sequence_asset_path="/Game/Trusted/SyntheticSequence",
    )


def _synthetic_integration(monkeypatch):
    integration = object.__new__(UnrealProductionControllerIntegration)
    captured = {}

    def fake_execute(request: CapabilityRequest):
        captured["request"] = request
        return {"status": "synthetic-accepted"}

    monkeypatch.setattr(integration, "execute", fake_execute)
    return integration, captured


def test_host_to_unreal_capability_preserves_host_trust(monkeypatch):
    integration, captured = _synthetic_integration(monkeypatch)
    trusted = _trusted_unreal_context()
    host = AgentControllerHost.for_unreal_production(integration, trusted)

    result = host.process_model_response(
        "ATLAS_CONTROLLER_REQUEST: "
        '{"capability":"production","provider":"unreal",'
        '"intent":"forged-model-intent",'
        '"context":{"production":true,"authorized_production":"FORGED",'
        '"intent":"FORGED","sequence_asset_path":"/Game/Forged"}}'
    )

    assert result is not None
    assert result.controller_executed is True
    request = captured["request"]
    assert request.normalized_provider == "unreal"
    assert request.normalized_capability == "production"
    assert request.context["production"] is True
    assert request.context["authorized_production"] is trusted.authorized_production
    assert request.context["intent"] is trusted.intent
    assert request.context["sequence_asset_path"] == trusted.sequence_asset_path
    assert result.classified.request.context["authorized_production"] is trusted.authorized_production
    assert result.classified.request.context["intent"] is trusted.intent
    assert result.classified.request.context["sequence_asset_path"] == trusted.sequence_asset_path
    assert result.classified.request.intent == "forged-model-intent"


def test_host_dispatch_binds_trusted_unreal_context(monkeypatch):
    integration, captured = _synthetic_integration(monkeypatch)
    trusted = _trusted_unreal_context()
    host = AgentControllerHost.for_unreal_production(integration, trusted)

    request = AgentTaskRequest(
        capability="production",
        provider="unreal",
        context={
            "production": True,
            "authorized_production": "FORGED",
            "intent": "FORGED",
            "sequence_asset_path": "/Game/Forged",
        },
        intent="explicit-model-intent",
    )

    result = host.dispatch(request)

    assert result.controller_executed is True
    admitted = captured["request"]
    assert admitted.normalized_provider == "unreal"
    assert admitted.normalized_capability == "production"
    assert admitted.context["production"] is True
    assert admitted.context["authorized_production"] is trusted.authorized_production
    assert admitted.context["intent"] is trusted.intent
    assert admitted.context["sequence_asset_path"] == trusted.sequence_asset_path
    assert result.classified.request.context["authorized_production"] is trusted.authorized_production
    assert result.classified.request.context["intent"] is trusted.intent
    assert result.classified.request.context["sequence_asset_path"] == trusted.sequence_asset_path
    assert result.classified.request.intent == "explicit-model-intent"


def test_host_without_unreal_trust_fails_closed(monkeypatch):
    integration, captured = _synthetic_integration(monkeypatch)
    process = AtlasAgentProcessRuntime(unreal_production=integration)
    host = AgentControllerHost(process=process)

    result = host.process_model_response(
        "ATLAS_CONTROLLER_REQUEST: "
        '{"capability":"production","provider":"unreal",'
        '"context":{"production":true}}'
    )

    assert result is not None
    assert result.controller_executed is False
    assert captured == {}
