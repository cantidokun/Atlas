import pytest

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_agent_cycle import BlenderAgentCycle, BlenderAgentCycleError


def _plan():
    return ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"})])


def test_cycle_installs_authorization_through_plan_lifecycle():
    plan = _plan()
    cycle = BlenderAgentCycle(authorize=lambda p: ActionAuthorization.issue(p.actions, "cycle-001"))

    assert cycle.authorize_plan(plan) is plan
    assert plan.authorized
    assert plan.authorization_id == "cycle-001"


def test_cycle_rejects_authorization_after_execution_has_started():
    plan = _plan()
    first = ActionAuthorization.issue(plan.actions, "cycle-002")
    plan.authorize(first)
    plan.record_result({"ok": True}, True)

    cycle = BlenderAgentCycle(authorize=lambda p: ActionAuthorization.issue(p.actions, "cycle-003"))
    with pytest.raises(BlenderAgentCycleError):
        cycle.authorize_plan(plan)


def test_cycle_rejects_authorization_for_mutated_plan():
    plan = _plan()
    plan.actions[0].arguments["file_name"] = "other.blend"
    stale = ActionAuthorization.issue([ActionSpec("inspect_scene", {"file_name": "scene.blend"})], "cycle-004")
    cycle = BlenderAgentCycle(authorize=lambda _: stale)

    with pytest.raises(BlenderAgentCycleError):
        cycle.authorize_plan(plan)
