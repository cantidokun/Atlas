"""Regression coverage for the high-level autonomous production facade."""
from unittest.mock import MagicMock

import pytest

from planning.action_plan import ActionPlan, ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.action_plan_sequence_adapter import ActionPlanSequenceAdapter
from planning.autonomous_production_orchestrator import AutonomousProductionOrchestrator
from planning.production_operation_lifecycle import ProductionOperationLifecycle


def authorized_plan() -> ActionPlan:
    plan = ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect")])
    plan.authorize(ActionAuthorization.issue(plan.actions, "auth-orchestrator"))
    return plan


def test_orchestrator_requires_adapter_and_admission_callable():
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(TypeError, match="adapter"):
        AutonomousProductionOrchestrator(None, lambda: True)
    with pytest.raises(TypeError, match="admission_ready"):
        AutonomousProductionOrchestrator(adapter, None)


def test_prepare_is_execution_free():
    plan = authorized_plan()
    created = []

    def factory(action):
        created.append(action)
        return MagicMock(spec=ProductionOperationLifecycle)

    orchestrator = AutonomousProductionOrchestrator(ActionPlanSequenceAdapter(factory), lambda: True)
    sequence = orchestrator.prepare(plan, sequence_id="shot-001")

    assert [step.name for step in sequence.steps] == ["inspect"]
    assert created == plan.actions
    sequence.steps[0].operation.run.assert_not_called()


def test_run_blocks_before_execution_when_admission_is_not_ready():
    plan = authorized_plan()
    operation = MagicMock(spec=ProductionOperationLifecycle)
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: operation),
        lambda: False,
    )

    result = orchestrator.run(plan, sequence_id="shot-001")

    assert result.blocked if hasattr(result, "blocked") else result.state.name == "BLOCKED"
    operation.run.assert_not_called()


def test_run_delegates_to_sequence_when_admitted():
    plan = authorized_plan()
    operation = MagicMock(spec=ProductionOperationLifecycle)
    operation.run.return_value = MagicMock(
        state=__import__("planning.production_operation_lifecycle", fromlist=["ProductionOperationState"]).ProductionOperationState.COMPLETED,
        receipt=MagicMock(),
        reason="verified",
    )
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: operation),
        lambda: True,
    )

    result = orchestrator.run(plan, sequence_id="shot-001")

    assert result.completed is True
    operation.run.assert_called_once()
