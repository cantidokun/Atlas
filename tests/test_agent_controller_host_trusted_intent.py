from controller.agent_controller_host import AgentControllerHost
from controller.trusted_unreal_context import TrustedUnrealContext


class _Integration:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return {"status": "ok"}


def test_unreal_production_intent_comes_from_trusted_context():
    integration = _Integration()
    trusted = TrustedUnrealContext(
        authorized_production="atlas-auth-001",
        intent="trusted-intent",
        sequence_asset_path="/Game/Atlas/Sequences/Soccer",
    )
    host = AgentControllerHost.for_unreal_production(integration, trusted)

    classified = host._classify(
        {
            "capability": "production",
            "provider": "unreal",
            "intent": "attacker-intent",
            "context": {"production": True},
        }
    )

    assert classified.request.intent == "trusted-intent"
    assert classified.request.context["authorized_production"] == "atlas-auth-001"
    assert classified.request.context["sequence_asset_path"] == "/Game/Atlas/Sequences/Soccer"
    assert classified.request.context["model_intent_mismatch"] is True


def test_unreal_production_without_model_intent_still_uses_trusted_intent():
    integration = _Integration()
    trusted = TrustedUnrealContext(
        authorized_production="atlas-auth-002",
        intent="trusted-intent-2",
        sequence_asset_path="/Game/Atlas/Sequences/Soccer",
    )
    host = AgentControllerHost.for_unreal_production(integration, trusted)

    classified = host._classify(
        {
            "capability": "production",
            "provider": "unreal",
            "context": {"production": True},
        }
    )

    assert classified.request.intent == "trusted-intent-2"
    assert "model_intent_mismatch" not in classified.request.context
