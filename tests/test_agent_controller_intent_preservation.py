"""Regression coverage for model intent preservation across admission."""

from controller.agent_controller_host import AgentControllerHost
from controller.capability_request import CapabilityRequest
from controller.trusted_unreal_context import TrustedUnrealContext
from planning.unreal_production_controller_integration import (
    UnrealProductionControllerIntegration,
)


def _trusted_unreal_context():
    from tests.test_trusted_unreal_context import _authorized, _intent

    intent = _intent("intent-preservation")
    return TrustedUnrealContext(
        authorized_production=_authorized(intent.intent_id),
        intent=intent,
        sequence_asset_path="/Game/Trusted/Sequence",
    )


def test_admission_preserves_only_canonical_capability_request_fields(monkeypatch):
    integration = object.__new__(UnrealProductionControllerIntegration)
    trusted = _trusted_unreal_context()
    captured = {}

    def fake_execute(request):
        captured["request"] = request
        return {"status": "accepted"}

    monkeypatch.setattr(integration, "execute", fake_execute)

    host = AgentControllerHost.for_unreal_production(integration, trusted)

    admission = host.process_model_response(
        "ATLAS_CONTROLLER_REQUEST: "
        '{"capability":"production","provider":"unreal",'
        '"context":{"production":true},"intent":"model-intent-2"}'
    )

    assert admission is not None
    assert admission.controller_executed is True
    assert admission.classified.request.intent == "model-intent-2"
    assert captured["request"].capability == "production"
    assert captured["request"].provider == "unreal"
    assert captured["request"].context["production"] is True


def test_capability_admission_does_not_expose_model_intent_on_canonical_request():
    request = CapabilityRequest(
        capability="production",
        provider="unreal",
        context={"production": True},
    )
    assert not hasattr(request, "intent")
