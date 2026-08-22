from planning.planner_provider import PlannerProvider
from planning.task_planner import TaskPlanProposal
from qwen.planner_provider import QwenPlannerProvider


class StubPlannerProvider(PlannerProvider):
    def __init__(self, proposal):
        self.proposal = proposal

    def build_proposal(self, model_output, *, allowed_tools=None):
        assert model_output == "stub-output"
        return self.proposal


def _proposal():
    return TaskPlanProposal(evidence=[], actions=[])


def test_planner_provider_boundary_is_model_agnostic():
    proposal = _proposal()
    provider = StubPlannerProvider(proposal)

    assert provider.build_proposal("stub-output") is proposal
    assert not isinstance(provider, QwenPlannerProvider)


def test_qwen_provider_implements_same_boundary_without_authorization():
    provider = QwenPlannerProvider()
    content = '''ATLAS_TASK_PLAN: {"evidence": [], "actions": []}'''

    proposal = provider.build_proposal(content)

    assert isinstance(proposal, TaskPlanProposal)
    assert proposal.evidence == []
    assert proposal.actions == []


def test_provider_output_does_not_authorize_actions():
    provider = QwenPlannerProvider()
    content = '''ATLAS_TASK_PLAN: {"evidence": [], "actions": [{"tool": "noop", "arguments": {}, "name": "noop"}]}'''

    proposal = provider.build_proposal(content)

    assert proposal is not None
    assert not hasattr(proposal, "authorization")
