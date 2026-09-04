import json

from controller.agent_controller_host import AgentControllerHost
from controller.trusted_unreal_context import TrustedUnrealContext


class _Integration:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return {"status": "accepted"}


def _host():
    integration = _Integration()
    trusted = TrustedUnrealContext(
        authorized_production={"authorization_id": "atlas-auth-001"},
        intent="render_soccer_sequence",
        sequence_asset_path="/Game/Atlas/Sequences/Soccer",
    )
    return AgentControllerHost.for_unreal_production(integration, trusted), integration


def _response(**payload):
    return "ATLAS_CONTROLLER_REQUEST:" + json.dumps(payload)


def test_model_cannot_replace_trusted_unreal_intent():
    host, integration = _host()
    result = host.process_model_response(
        _response(
            capability="production",
            provider="unreal",
            intent="attacker_intent",
            context={"production": True},
        )
    )

    assert result is not None
    assert result.controller_executed is True
    assert result.classified.request.intent == "render_soccer_sequence"
    assert result.classified.request.context["authorized_production"]["authorization_id"] == "atlas-auth-001"
    assert result.classified.request.context["sequence_asset_path"] == "/Game/Atlas/Sequences/Soccer"
    assert result.classified.request.context["model_intent_mismatch"] is True
    assert len(integration.requests) == 1


def test_model_cannot_disable_trusted_unreal_production_marker():
    host, integration = _host()
    result = host.process_model_response(
        _response(
            capability="production",
            provider="unreal",
            intent="render_soccer_sequence",
            context={"production": False},
        )
    )

    assert result is not None
    assert result.controller_executed is True
    assert result.classified.request.context["production"] is True
    assert result.classified.request.context["model_production_mismatch"] is True
    assert len(integration.requests) == 1


def test_host_requires_executable_unreal_integration():
    trusted = TrustedUnrealContext(
        authorized_production={"authorization_id": "atlas-auth-001"},
        intent="render_soccer_sequence",
        sequence_asset_path="/Game/Atlas/Sequences/Soccer",
    )

    try:
        AgentControllerHost.for_unreal_production(None, trusted)
    except TypeError as exc:
        assert "callable execute method" in str(exc)
    else:
        raise AssertionError("host accepted an integration without execute")
