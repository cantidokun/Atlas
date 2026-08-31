"""Regression coverage for the authorized ActionPlan production bridge."""
from unittest.mock import MagicMock

import pytest

from planning.action_plan import ActionPlan, ActionSpec
from planning.action_plan_sequence_adapter import ActionPlanSequenceAdapter
from planning.production_operation_lifecycle import ProductionOperationLifecycle


def authorized_plan():
    plan = ActionPlan([])
    plan.actions = [
        ActionSpec(tool="create_collection", arguments={"name": "Field"}, name="create"),
        ActionSpec(tool="move_object", arguments={"object": "Ball", "collection": "Field"}, name="move"),
    ]
    plan.authorize_with_id("auth-001")
    return plan


def test_adapter_requires_authorized_plan():
    plan = ActionPlan([])
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(RuntimeError, match="must be authorized"):
        adapter.to_sequence(plan)


def test_adapter_rejects_partially_executed_plan():
    plan = authorized_plan()
    plan.current_index = 1
    plan.completed.append({"index": 0, "name": "create"})
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(RuntimeError, match="must be pristine"):
        adapter.to_sequence(plan)


def test_adapter_rejects_failed_plan():
    plan = authorized_plan()
    plan.failed = {"index": 0, "name": "create", "success": False}
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(RuntimeError, match="must be pristine"):
        adapter.to_sequence(plan)


def test_adapter_rejects_empty_authorized_plan():
    plan = ActionPlan([])
    plan.authorize_with_id("auth-empty")
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(ValueError, match="at least one action"):
        adapter.to_sequence(plan)


def test_adapter_maps_authorized_actions_in_order_without_execution():
    plan = authorized_plan()
    created = []

    def factory(action):
        created.append(action)
        return MagicMock(spec=ProductionOperationLifecycle)

    sequence = ActionPlanSequenceAdapter(factory).to_sequence(plan, sequence_id="shot-001")
    assert [step.name for step in sequence.steps] == ["create", "move"]
    assert created == plan.actions
    for step in sequence.steps:
        step.operation.run.assert_not_called()


def test_adapter_requires_callable_factory():
    with pytest.raises(TypeError, match="operation_factory must be callable"):
        ActionPlanSequenceAdapter(None)
