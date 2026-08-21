from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_agent_cycle import BlenderCycleResult
from planning.blender_agent_state import BlenderAgentState, BlenderObservation
from planning.blender_execution_coordinator import BlenderExecutionStep
from planning.blender_replanning import BlenderReplanner
from planning.blender_task_planner import BlenderTaskIntent


def task():
    return BlenderTaskIntent("task-r1", "Clean the scene", (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),))


def result(complete=False):
    step = BlenderExecutionStep(0, "inspect_scene", {"file_name": "scene.blend"}, {"status": "ok"}, True, complete)
    return BlenderCycleResult(ActionPlan(actions=list(task().actions)), step)


def test_replanner_uses_verified_evidence_for_next_intent():
    state = BlenderAgentState(task=task())
    state.record_cycle(result())

    next_task = BlenderTaskIntent("task-r2", "Fix the warning", (ActionSpec("inspect_scene_health", {"file_name": "scene.blend"}),))
    replanner = BlenderReplanner(lambda current: next_task)

    decision = replanner.decide(state, BlenderObservation("scene_health", {"warning": "unapplied_transform"}))

    assert decision.satisfied is False
    assert decision.next_intent == next_task
    assert state.latest_observation.facts["warning"] == "unapplied_transform"


def test_replanner_stops_when_objective_is_verified_complete():
    state = BlenderAgentState(task=task())
    state.record_cycle(result(complete=True))
    replanner = BlenderReplanner(lambda _: None)

    decision = replanner.decide(state, BlenderObservation("verification", {"clean": True}))

    assert decision.satisfied is True
    assert decision.next_intent is None
