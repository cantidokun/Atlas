import pytest

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_agent_cycle import BlenderAgentCycle, BlenderAgentCycleError
from planning.blender_task_planner import BlenderTaskIntent


def make_intent():
    return BlenderTaskIntent(
        task_id="task-cycle-001",
        objective="Inspect the soccer scene.",
        actions=(ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )


def make_authorization(plan):
    return ActionAuthorization.for_plan(plan, approver="test")


def test_cycle_builds_authorizes_and_advances_one_verified_action():
    cycle = BlenderAgentCycle(authorize=make_authorization)
    plan = cycle.authorize_plan(cycle.build_plan(make_intent()))

    checkpoints = []
    result = cycle.advance(
        plan,
        execute=lambda tool, arguments: {"status": "ok", "tool": tool, "arguments": arguments},
        verify=lambda tool, arguments, execution: True,
        checkpoint=checkpoints.append,
    )

    assert result.step is not None
    assert result.step.verified is True
    assert result.step.complete is True
    assert result.plan.complete is True
    assert len(checkpoints) == 1


def test_cycle_refuses_execution_without_authorization():
    cycle = BlenderAgentCycle(authorize=make_authorization)
    plan = cycle.build_plan(make_intent())

    with pytest.raises(Exception, match="authorization"):
        cycle.advance(plan, execute=lambda *_: {"status": "ok"})


def test_cycle_refuses_missing_authorization_provider():
    cycle = BlenderAgentCycle()
    plan = cycle.build_plan(make_intent())

    with pytest.raises(BlenderAgentCycleError, match="authorization provider"):
        cycle.authorize_plan(plan)


def test_cycle_rejects_authorization_for_different_plan():
    cycle = BlenderAgentCycle(authorize=lambda _plan: ActionAuthorization.for_plan(
        ActionPlan(actions=[ActionSpec("inspect_scene", {"file_name": "other.blend"})]),
        approver="test",
    ))

    with pytest.raises(BlenderAgentCycleError, match="does not match"):
        cycle.authorize_plan(cycle.build_plan(make_intent()))
