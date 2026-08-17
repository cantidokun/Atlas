import pytest

from planning.action_plan import ActionPlan, ActionSpec
from planning.digital_twin_adapter_contract import ToolActionResult
from planning.digital_twin_adapter_runtime import AdapterExecutionBridge
from planning.digital_twin_representation import (
    ProductionTool,
    create_representation_contract,
)
from planning.action_authorization import ActionAuthorization


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def apply_authorized_action(self, representation, action_name, arguments):
        self.calls.append((representation.representation_id, action_name, dict(arguments)))
        return ToolActionResult(
            representation_id=representation.representation_id,
            action_id="unreal-action-001",
            success=True,
            evidence_ids=("evidence-001",),
        )


def representation():
    return create_representation_contract(
        "field-001",
        "field-001-unreal-r1",
        "field-001-r1",
        ProductionTool.UNREAL,
        "UE_WORLD:Field01",
    )


def authorized_plan():
    plan = ActionPlan([ActionSpec(tool="unreal.modify_actor", arguments={"entity_id": "goal-left"})])
    plan.authorize(ActionAuthorization.issue(plan.actions, "auth-001"))
    return plan


def test_bridge_executes_only_authorized_next_action():
    adapter = FakeAdapter()
    plan = authorized_plan()
    result = AdapterExecutionBridge(adapter).execute_next(plan, representation(), "field-001-r1")

    assert result.success is True
    assert len(adapter.calls) == 1
    assert adapter.calls[0][1] == "unreal.modify_actor"
    assert plan.complete is True


def test_bridge_rejects_unauthorized_plan():
    adapter = FakeAdapter()
    plan = ActionPlan([ActionSpec(tool="unreal.modify_actor", arguments={})])
    with pytest.raises(RuntimeError, match="valid action authorization"):
        AdapterExecutionBridge(adapter).execute_next(plan, representation(), "field-001-r1")
    assert adapter.calls == []


def test_bridge_rejects_stale_representation_before_tool_call():
    adapter = FakeAdapter()
    with pytest.raises(ValueError, match="representation is stale"):
        AdapterExecutionBridge(adapter).execute_next(
            authorized_plan(), representation(), "field-001-r2"
        )
    assert adapter.calls == []
