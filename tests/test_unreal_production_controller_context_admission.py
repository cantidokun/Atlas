import pytest

from controller.capability_request import CapabilityRequest
from planning.unreal_production_controller_integration import (
    UnrealProductionControllerIntegration,
)


def _request(context):
    return CapabilityRequest(
        capability="production",
        provider="unreal",
        intent="render_soccer_sequence",
        context=context,
    )


class _Executor:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return {"status": "accepted"}


def _trusted_context():
    return {
        "production": True,
        "authorized_production": {"authorization_id": "atlas-auth-001"},
        "intent": "render_soccer_sequence",
        "sequence_asset_path": "/Game/Atlas/Sequences/Soccer",
    }


def test_unreal_integration_accepts_complete_host_owned_context():
    executor = _Executor()
    integration = UnrealProductionControllerIntegration(executor)

    result = integration.execute(_request(_trusted_context()))

    assert result == {"status": "accepted"}
    assert len(executor.requests) == 1


def test_unreal_integration_rejects_missing_trusted_context():
    executor = _Executor()
    integration = UnrealProductionControllerIntegration(executor)
    context = _trusted_context()
    del context["authorized_production"]

    with pytest.raises(ValueError, match="missing trusted context"):
        integration.execute(_request(context))

    assert executor.requests == []


def test_unreal_integration_rejects_non_production_marker():
    executor = _Executor()
    integration = UnrealProductionControllerIntegration(executor)
    context = _trusted_context()
    context["production"] = False

    with pytest.raises(ValueError, match="trusted production context"):
        integration.execute(_request(context))

    assert executor.requests == []


def test_unreal_integration_rejects_empty_trusted_intent():
    executor = _Executor()
    integration = UnrealProductionControllerIntegration(executor)
    context = _trusted_context()
    context["intent"] = "   "

    with pytest.raises(ValueError, match="trusted intent"):
        integration.execute(_request(context))

    assert executor.requests == []


def test_unreal_integration_rejects_empty_trusted_sequence_path():
    executor = _Executor()
    integration = UnrealProductionControllerIntegration(executor)
    context = _trusted_context()
    context["sequence_asset_path"] = ""

    with pytest.raises(ValueError, match="trusted sequence_asset_path"):
        integration.execute(_request(context))

    assert executor.requests == []
