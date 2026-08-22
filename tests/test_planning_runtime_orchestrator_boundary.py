from planning.action_plan import ActionSpec
from planning.planner_provider import PlannerProvider
from planning.planning_runtime import PlanningRuntime
from planning.task_planner import TaskPlanProposal
from evidence_plan import EvidenceRequest


class Provider(PlannerProvider):
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
                arguments={
                    "object_name": "FIELD_SURFACE",
                    "location": {"x": 1, "y": 2, "z": 3},
                },
                name="move field",
            )
        ],
    )


def test_runtime_builds_authorized_orchestrator_without_executing_tools():
    runtime = PlanningRuntime(Provider(_proposal()))

    orchestrator = runtime.build_authorized_orchestrator(
        "provider output",
        authorization_id="runtime-orchestrator-auth-001",
        allowed_tools={"inspect_object", "move_object"},
    )

    assert orchestrator is not None
    assert orchestrator.next_phase() == "EVIDENCE"
    assert orchestrator.action_plan.authorized is True
    assert orchestrator.action_plan.authorization_id == "runtime-orchestrator-auth-001"
    assert orchestrator.action_plan.current_index == 0


def test_authorized_orchestrator_executes_evidence_then_exact_authorized_action():
    runtime = PlanningRuntime(Provider(_proposal()))
    orchestrator = runtime.build_authorized_orchestrator(
        "provider output",
        authorization_id="runtime-orchestrator-auth-002",
        allowed_tools={"inspect_object", "move_object"},
    )
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return {"ok": True, "tool": tool}

    evidence_result = orchestrator.acquire_next_evidence(execute)
    action_result = orchestrator.execute_next_action(execute)

    assert evidence_result["ok"] is True
    assert action_result["ok"] is True
    assert calls == [
        ("inspect_object", {"object_name": "FIELD_SURFACE"}),
        ("move_object", {"object_name": "FIELD_SURFACE", "location": {"x": 1, "y": 2, "z": 3}}),
    ]
    assert orchestrator.evidence_complete is True
    assert orchestrator.action_complete is True
    assert orchestrator.next_phase() == "COMPLETE"
    assert orchestrator.action_plan.authorization_id == "runtime-orchestrator-auth-002"
