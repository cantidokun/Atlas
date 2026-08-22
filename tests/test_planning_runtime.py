import pytest

from planning.planner_provider import PlannerProvider
from planning.planning_runtime import PlanningRuntime
from planning.task_planner import TaskPlanProposal


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
