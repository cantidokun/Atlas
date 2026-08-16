import pytest

from action_plan import ActionPlan
from evidence_plan import EvidencePlan
from planning_orchestrator import PlanningOrchestrator
from task_planner import TaskPlanValidationError, build_task_plan, instantiate_plans


ALLOWED_TOOLS = {"inspect_scene", "inspect_object_relationship", "move_object"}


def _proposal():
    return {
        "evidence": [
            {
                "tool": "inspect_scene",
                "arguments": {"file_name": "scene.blend"},
                "name": "scene",
            }
        ],
        "actions": [
            {
                "tool": "move_object",
                "arguments": {
                    "file_name": "scene.blend",
                    "object_name": "A",
                    "location": [1, 0, 0],
                },
                "name": "move A",
            }
        ],
    }


def test_valid_proposal_instantiates_inert_plans():
    proposal = build_task_plan(_proposal(), allowed_tools=ALLOWED_TOOLS)
    evidence, actions = instantiate_plans(proposal)

    assert isinstance(evidence, EvidencePlan)
    assert isinstance(actions, ActionPlan)
    assert evidence.complete is False
    assert actions.complete is False


def test_disallowed_tool_is_rejected_before_execution():
    proposal = _proposal()
    proposal["actions"][0]["tool"] = "dangerous_tool"

    with pytest.raises(TaskPlanValidationError, match="not allowed"):
        build_task_plan(proposal, allowed_tools=ALLOWED_TOOLS)


def test_planner_cannot_execute_unverified_plan_directly():
    proposal = build_task_plan(_proposal(), allowed_tools=ALLOWED_TOOLS)
    evidence, actions = instantiate_plans(proposal)
    orchestrator = PlanningOrchestrator(evidence, actions)

    with pytest.raises(RuntimeError, match="evidence"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})


def test_evidence_unlocks_action_but_does_not_authorize_extra_tools():
    proposal = build_task_plan(_proposal(), allowed_tools=ALLOWED_TOOLS)
    evidence, actions = instantiate_plans(proposal)
    orchestrator = PlanningOrchestrator(evidence, actions)

    calls = []

    def execute(tool, args):
        calls.append((tool, args))
        if tool == "inspect_scene":
            return {"objects": 1}
        return {"status": "moved"}

    orchestrator.acquire_next_evidence(execute)
    orchestrator.execute_next_action(execute)

    assert [tool for tool, _ in calls] == ["inspect_scene", "move_object"]
    assert orchestrator.next_phase() == "COMPLETE"
