import pytest

from planning.planner_provider import PlannerProvider
from planning.planning_runtime import PlanningRuntime
from planning.task_planner import (
    TaskPlanProposal,
    TaskPlanValidationError,
    instantiate_authorized_plans,
)
from action_plan import ActionSpec
from evidence_plan import EvidenceRequest


class GenericProvider(PlannerProvider):
    def __init__(self, proposal):
        self.proposal = proposal

    def build_proposal(self, model_output, *, allowed_tools=None):
        return self.proposal


def _proposal():
    return TaskPlanProposal(
        evidence=[
            EvidenceRequest(
                tool="inspect_object",
                arguments={"object_name": "FIELD_SURFACE"},
                name="inspect field",
            )
        ],
        actions=[
            ActionSpec(
                tool="move_object",
                arguments={"object_name": "FIELD_SURFACE", "location": {"x": 1, "y": 2, "z": 3}},
                name="move field",
            )
        ],
    )


def test_provider_neutral_runtime_reaches_authorized_action_plan():
    proposal = _proposal()
    runtime = PlanningRuntime(GenericProvider(proposal))

    result = runtime.build_proposal("provider-specific output")
    evidence_plan, action_plan = instantiate_authorized_plans(
        result,
        authorization_id="provider-neutral-auth-001",
    )

    assert result is proposal
    assert evidence_plan.requests == proposal.evidence
    assert action_plan.actions == proposal.actions
    assert action_plan.authorized is True
    assert action_plan.authorization_id == "provider-neutral-auth-001"
    assert action_plan.current_index == 0
    assert action_plan.next_action == proposal.actions[0]


def test_authorization_is_bound_to_exact_provider_proposal():
    proposal = _proposal()
    _, action_plan = instantiate_authorized_plans(
        proposal,
        authorization_id="provider-neutral-auth-002",
    )

    action_plan.record_result({"ok": True}, True)

    assert action_plan.complete is True
    assert action_plan.authorization_id == "provider-neutral-auth-002"
    assert action_plan.completed[0]["tool"] == "move_object"


def test_disallowed_provider_output_never_reaches_authorization():
    proposal = _proposal()

    class ValidatingProvider(PlannerProvider):
        def build_proposal(self, model_output, *, allowed_tools=None):
            if allowed_tools is not None and "move_object" not in allowed_tools:
                raise TaskPlanValidationError("Tool is not allowed: move_object")
            return proposal

    runtime = PlanningRuntime(ValidatingProvider())

    with pytest.raises(TaskPlanValidationError, match="not allowed"):
        runtime.build_proposal("provider output", allowed_tools={"inspect_object"})
