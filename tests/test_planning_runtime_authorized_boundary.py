import pytest

from action_plan import ActionSpec
from planning.planner_provider import PlannerProvider
from planning.planning_runtime import PlanningRuntime
from planning.task_planner import TaskPlanProposal, TaskPlanValidationError


class ProposalProvider(PlannerProvider):
    def __init__(self, proposal):
        self.proposal = proposal
        self.calls = []

    def build_proposal(self, model_output, *, allowed_tools=None):
        self.calls.append((model_output, allowed_tools))
        return self.proposal


def _proposal():
    return TaskPlanProposal(
        evidence=[],
        actions=[
            ActionSpec(
                tool="move_object",
                arguments={"object_name": "FIELD_SURFACE", "location": {"x": 1, "y": 2, "z": 3}},
                name="move field",
            )
        ],
    )


def test_build_authorized_plans_returns_explicit_receipt_bound_plans():
    provider = ProposalProvider(_proposal())
    runtime = PlanningRuntime(provider)

    result = runtime.build_authorized_plans(
        "model output",
        authorization_id="runtime-auth-001",
        allowed_tools={"move_object"},
    )

    assert result is not None
    evidence_plan, action_plan = result
    assert action_plan.authorized is True
    assert action_plan.authorization_id == "runtime-auth-001"
    assert action_plan.current_index == 0
    assert action_plan.next_action.tool == "move_object"
    assert provider.calls == [("model output", {"move_object"})]


def test_build_authorized_plans_does_not_reauthorize_after_proposal_is_returned():
    class CountingProvider(PlannerProvider):
        def __init__(self):
            self.proposal = _proposal()
            self.calls = 0

        def build_proposal(self, model_output, *, allowed_tools=None):
            self.calls += 1
            return self.proposal

    provider = CountingProvider()
    runtime = PlanningRuntime(provider)
    evidence_plan, action_plan = runtime.build_authorized_plans(
        "model output",
        authorization_id="runtime-auth-002",
    )

    assert provider.calls == 1
    assert evidence_plan.requests == []
    assert action_plan.authorization_id == "runtime-auth-002"


def test_disallowed_provider_output_is_rejected_before_authorization():
    proposal = _proposal()

    class RejectingProvider(PlannerProvider):
        def build_proposal(self, model_output, *, allowed_tools=None):
            if allowed_tools is not None and "move_object" not in allowed_tools:
                raise TaskPlanValidationError("Tool is not allowed: move_object")
            return proposal

    runtime = PlanningRuntime(RejectingProvider())

    with pytest.raises(TaskPlanValidationError, match="not allowed"):
        runtime.build_authorized_plans(
            "model output",
            authorization_id="runtime-auth-003",
            allowed_tools={"inspect_object"},
        )


def test_authorized_action_plan_rejects_mutation_before_execution_receipt_is_replaced():
    runtime = PlanningRuntime(ProposalProvider(_proposal()))
    _, action_plan = runtime.build_authorized_plans(
        "model output",
        authorization_id="runtime-auth-004",
    )

    original = action_plan.actions[0]
    action_plan.actions[0] = ActionSpec(
        tool=original.tool,
        arguments={**original.arguments, "location": {"x": 99, "y": 2, "z": 3}},
        name=original.name,
    )

    assert action_plan.authorized is False
    assert action_plan.authorization_id == "runtime-auth-004"
    with pytest.raises(RuntimeError, match="requires valid authorization"):
        action_plan.record_result({"ok": True}, True)
