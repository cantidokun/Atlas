import pytest

from planning.action_plan import ActionSpec
from planning.planner_provider import PlannerProvider
from planning.planning_runtime import PlanningRuntime
from planning.task_planner import TaskPlanProposal, TaskPlanValidationError


class StubProvider(PlannerProvider):
    def __init__(self, result):
        self.result = result

    def build_proposal(self, model_output, *, allowed_tools=None):
        return self.result


def test_runtime_is_provider_agnostic_and_returns_stable_proposal():
    proposal = TaskPlanProposal(evidence=[], actions=[])
    runtime = PlanningRuntime(StubProvider(proposal))

    assert runtime.build_proposal("any-model-output") is proposal


def test_runtime_rejects_non_provider():
    with pytest.raises(TypeError, match="provider must implement PlannerProvider"):
        PlanningRuntime(object())


def test_runtime_rejects_provider_returning_wrong_type():
    runtime = PlanningRuntime(StubProvider({"actions": []}))

    with pytest.raises(ValueError, match="invalid proposal"):
        runtime.build_proposal("output")


def test_runtime_does_not_authorize_provider_output():
    proposal = TaskPlanProposal(evidence=[], actions=[])
    runtime = PlanningRuntime(StubProvider(proposal))

    result = runtime.build_proposal("output")

    assert result is proposal
    assert not hasattr(result, "authorization")


def test_runtime_build_authorized_plans_binds_one_receipt_to_exact_actions():
    actions = [ActionSpec(tool="move_object", arguments={"object_name": "A"}, name="move")]
    proposal = TaskPlanProposal(evidence=[], actions=actions)
    runtime = PlanningRuntime(StubProvider(proposal))

    evidence_plan, action_plan = runtime.build_authorized_plans(
        "output",
        authorization_id="runtime-auth-001",
        allowed_tools={"move_object"},
    )

    assert evidence_plan.requests == []
    assert action_plan.authorized is True
    assert action_plan.authorization_id == "runtime-auth-001"
    assert action_plan.next_action is actions[0]


def test_runtime_validates_before_authorizing():
    actions = [ActionSpec(tool="delete_object", arguments={"object_name": "A"})]
    proposal = TaskPlanProposal(evidence=[], actions=actions)
    runtime = PlanningRuntime(StubProvider(proposal))

    with pytest.raises(TaskPlanValidationError):
        runtime.build_authorized_plans(
            "output",
            authorization_id="runtime-auth-002",
            allowed_tools={"move_object"},
        )
