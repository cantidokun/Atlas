import pytest

from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_agent_cycle import BlenderCycleResult
from planning.blender_agent_state import BlenderAgentState, BlenderObservation
from planning.blender_task_planner import BlenderTaskIntent
from planning.blender_execution_coordinator import BlenderExecutionStep


def make_task():
    return BlenderTaskIntent(
        task_id="state-001",
        objective="Inspect scene",
        actions=(ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )


def make_step(*, verified=True, complete=False):
    return BlenderExecutionStep(
        action=ActionSpec("inspect_scene", {"file_name": "scene.blend"}),
        result={"status": "ok"},
        verified=verified,
        complete=complete,
    )


def test_state_accepts_only_verified_observations():
    state = BlenderAgentState(task=make_task())
    state.record_observation(BlenderObservation("scene", {"objects": 10}))
    assert state.latest_observation.facts["objects"] == 10

    with pytest.raises(ValueError, match="unverified observations"):
        state.record_observation(BlenderObservation("scene", {}, verified=False))


def test_state_accepts_only_verified_cycles():
    state = BlenderAgentState(task=make_task())
    plan = ActionPlan(actions=list(make_task().actions))
    state.record_cycle(BlenderCycleResult(plan, make_step()))
    assert state.latest_cycle is not None

    with pytest.raises(ValueError, match="unverified execution"):
        state.record_cycle(BlenderCycleResult(plan, make_step(verified=False)))


def test_objective_satisfied_requires_verified_complete_step():
    state = BlenderAgentState(task=make_task())
    assert state.objective_satisfied is False
    plan = ActionPlan(actions=list(make_task().actions))
    state.record_cycle(BlenderCycleResult(plan, make_step(complete=True)))
    assert state.objective_satisfied is True
