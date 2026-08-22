from planning.planner_provider import PlannerProvider
from planning.planner_runtime import PlannerRuntime
from planning.task_planner import TaskPlanProposal


class StubProvider(PlannerProvider):
    def __init__(self):
        self.calls = []

    def build_proposal(self, model_output, *, allowed_tools=None):
        self.calls.append((model_output, allowed_tools))
        return TaskPlanProposal(evidence=[], actions=[])


def test_runtime_delegates_to_provider_without_authorizing():
    provider = StubProvider()
    runtime = PlannerRuntime(provider)
    proposal = runtime.build_proposal("model-output", allowed_tools={"inspect"})

    assert proposal is not None
    assert provider.calls == [("model-output", {"inspect"})]
    assert not hasattr(proposal, "authorization")


def test_runtime_rejects_non_provider():
    try:
        PlannerRuntime(object())
    except TypeError as exc:
        assert "PlannerProvider" in str(exc)
    else:
        raise AssertionError("expected TypeError")
