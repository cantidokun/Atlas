"""Regression coverage for the high-level autonomous production facade."""
from unittest.mock import MagicMock

import pytest

from planning.action_plan import ActionPlan, ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.action_plan_sequence_adapter import ActionPlanSequenceAdapter
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_planner import AutonomousProductionGoalPlanner
from planning.autonomous_production_orchestrator import AutonomousProductionOrchestrator
from planning.blender_autonomous_admission import BlenderAutonomousAdmission
from planning.blender_task_planner import BlenderTaskPlanner
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.production_operation_lifecycle import ProductionOperationState


class FakeAdmission(BlenderAutonomousAdmission):
    """Test-only stand-in preserving the canonical admission type contract."""

    def __init__(self, ready: bool):
        self._ready = ready

    @property
    def ready(self) -> bool:
        return self._ready


def authorized_plan() -> ActionPlan:
    plan = ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect")])
    plan.authorize(ActionAuthorization.issue(plan.actions, "auth-orchestrator"))
    return plan


def authorize_plan(plan: ActionPlan) -> ActionAuthorization:
    return ActionAuthorization.issue(plan.actions, "goal-authorized")


def test_orchestrator_requires_canonical_adapter_and_admission():
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(TypeError, match="adapter"):
        AutonomousProductionOrchestrator(None, FakeAdmission(True))
    with pytest.raises(TypeError, match="admission"):
        AutonomousProductionOrchestrator(adapter, None)


def test_orchestrator_rejects_invalid_goal_planner_and_authorizer():
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(TypeError, match="goal_planner"):
        AutonomousProductionOrchestrator(adapter, FakeAdmission(True), goal_planner=object())
    planner = AutonomousProductionGoalPlanner(BlenderTaskPlanner())
    with pytest.raises(TypeError, match="authorize"):
        AutonomousProductionOrchestrator(adapter, FakeAdmission(True), goal_planner=planner, authorize=object())


def test_prepare_is_execution_free():
    plan = authorized_plan()
    created = []

    def factory(action):
        created.append(action)
        return MagicMock(spec=ProductionOperationLifecycle)

    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(factory),
        FakeAdmission(True),
    )
    sequence = orchestrator.prepare(plan, sequence_id="shot-001")

    assert [step.name for step in sequence.steps] == ["inspect"]
    assert created == plan.actions
    sequence.steps[0].operation.run.assert_not_called()


def test_prepare_goal_uses_canonical_goal_planner_and_explicit_authorizer():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )
    created = []
    authorized = []

    def factory(action):
        created.append(action)
        return MagicMock(spec=ProductionOperationLifecycle)

    def authorize(plan):
        authorized.append(plan)
        return authorize_plan(plan)

    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(factory),
        FakeAdmission(True),
        goal_planner=AutonomousProductionGoalPlanner(BlenderTaskPlanner()),
        authorize=authorize,
    )

    sequence = orchestrator.prepare_goal(goal, sequence_id="shot-001")

    assert [step.name for step in sequence.steps] == ["inspect"]
    assert created[0].tool == "inspect_scene"
    assert len(authorized) == 1
    assert authorized[0].authorized is True
    sequence.steps[0].operation.run.assert_not_called()


def test_prepare_goal_requires_goal_planner_and_authorizer():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    adapter = ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle))
    with pytest.raises(RuntimeError, match="goal_planner is required"):
        AutonomousProductionOrchestrator(adapter, FakeAdmission(True)).prepare_goal(goal)

    orchestrator = AutonomousProductionOrchestrator(
        adapter,
        FakeAdmission(True),
        goal_planner=AutonomousProductionGoalPlanner(BlenderTaskPlanner()),
    )
    with pytest.raises(RuntimeError, match="authorize is required"):
        orchestrator.prepare_goal(goal)


def test_prepare_goal_rejects_authorizer_that_returns_wrong_type():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle)),
        FakeAdmission(True),
        goal_planner=AutonomousProductionGoalPlanner(BlenderTaskPlanner()),
        authorize=lambda _plan: object(),
    )
    with pytest.raises(TypeError, match="ActionAuthorization"):
        orchestrator.prepare_goal(goal)


def test_prepare_goal_rejects_authorization_for_different_plan():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    other = ActionPlan([ActionSpec("move_object", {"object_name": "player", "location": [1, 2, 3]})])
    mismatched = ActionAuthorization.issue(other.actions, "wrong-plan")
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: MagicMock(spec=ProductionOperationLifecycle)),
        FakeAdmission(True),
        goal_planner=AutonomousProductionGoalPlanner(BlenderTaskPlanner()),
        authorize=lambda _plan: mismatched,
    )
    with pytest.raises(RuntimeError, match="does not match the exact action plan"):
        orchestrator.prepare_goal(goal)


def test_run_blocks_before_execution_when_admission_is_not_ready():
    plan = authorized_plan()
    operation = MagicMock(spec=ProductionOperationLifecycle)
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: operation),
        FakeAdmission(False),
    )

    result = orchestrator.run(plan, sequence_id="shot-001")

    assert result.state.name == "BLOCKED"
    operation.run.assert_not_called()


def test_run_delegates_to_sequence_when_admitted():
    plan = authorized_plan()
    operation = MagicMock(spec=ProductionOperationLifecycle)
    operation.run.return_value = MagicMock(
        state=ProductionOperationState.COMPLETED,
        receipt=MagicMock(),
        reason="verified",
    )
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: operation),
        FakeAdmission(True),
    )

    result = orchestrator.run(plan, sequence_id="shot-001")

    assert result.completed is True
    operation.run.assert_called_once()


def test_run_goal_compiles_authorizes_then_delegates_without_bypassing_admission():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )
    operation = MagicMock(spec=ProductionOperationLifecycle)
    operation.run.return_value = MagicMock(
        state=ProductionOperationState.COMPLETED,
        receipt=MagicMock(),
        reason="verified",
    )
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: operation),
        FakeAdmission(True),
        goal_planner=AutonomousProductionGoalPlanner(BlenderTaskPlanner()),
        authorize=authorize_plan,
    )

    result = orchestrator.run_goal(goal, sequence_id="shot-001")

    assert result.completed is True
    operation.run.assert_called_once()


def test_run_goal_does_not_execute_when_admission_rejects():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    operation = MagicMock(spec=ProductionOperationLifecycle)
    orchestrator = AutonomousProductionOrchestrator(
        ActionPlanSequenceAdapter(lambda _action: operation),
        FakeAdmission(False),
        goal_planner=AutonomousProductionGoalPlanner(BlenderTaskPlanner()),
        authorize=authorize_plan,
    )

    result = orchestrator.run_goal(goal, sequence_id="shot-001")

    assert result.state is ProductionOperationState.BLOCKED
    operation.run.assert_not_called()
