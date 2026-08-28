"""Tests for the concrete agent-to-controller production request boundary."""

import pytest

from controller.agent_entrypoint_contract import AgentControllerHandoff
from planning.agent_controller_production_request import AgentControllerProductionRequest


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def execute(self, handoff):
        self.calls.append(handoff)
        return {"status": "executed", "intent_id": handoff.request.intent_id}


def _handoff():
    return AgentControllerHandoff.from_fields(
        capability="production",
        provider="unreal",
        target_entity_ids=("FIELD_SURFACE",),
        intent_id="agent-produced-request",
        description="agent-originated Unreal production request",
        context={"production": True},
    )


def test_submit_delegates_explicit_handoff_without_reselection():
    runtime = FakeRuntime()
    handoff = _handoff()

    result = AgentControllerProductionRequest(runtime).submit(handoff)

    assert result == {
        "status": "executed",
        "intent_id": "agent-produced-request",
    }
    assert runtime.calls == [handoff]


def test_submit_rejects_raw_request_shape():
    runtime = FakeRuntime()
    with pytest.raises(TypeError, match="AgentControllerHandoff"):
        AgentControllerProductionRequest(runtime).submit(object())
