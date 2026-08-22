from dataclasses import dataclass

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportResponse


@dataclass
class SequenceTransport:
    state: dict

    def __post_init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        if request.operation_name == "set_actor_location":
            self.state[request.entity_ids[0]]["location"] = dict(request.arguments["location"])
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=self.state,
            error="",
            source="sequence-test",
        )


def test_executor_runs_compound_location_sequence_in_order():
    state = {"FIELD_SURFACE": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}}
    transport = SequenceTransport(state)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    planner = UnrealTaskPlanner()
    plan = planner.plan_actor_location_sequence(
        UnrealTaskIntent("sequence-execution-1", "run ordered field motion", ("FIELD_SURFACE",)),
        (
            {"x": 100.0, "y": 200.0, "z": 300.0},
            {"x": 110.0, "y": 210.0, "z": 310.0},
        ),
    )

    result = executor.execute(plan, "sequence-auth-001")

    assert result.success is True
    assert len(result.evidence_ledger) == 5
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors",
        "set_actor_location",
        "inspect_target_actors",
        "set_actor_location",
        "inspect_target_actors",
    ]
    assert state["FIELD_SURFACE"]["location"] == {"x": 110.0, "y": 210.0, "z": 310.0}


def test_sequence_plan_keeps_each_mutation_adjacent_to_its_proof():
    plan = UnrealTaskPlanner().plan_actor_location_sequence(
        UnrealTaskIntent("sequence-shape-1", "run ordered field motion", ("FIELD_SURFACE",)),
        (
            {"x": 1.0, "y": 2.0, "z": 3.0},
            {"x": 4.0, "y": 5.0, "z": 6.0},
            {"x": 7.0, "y": 8.0, "z": 9.0},
        ),
    )

    operations = plan.operations
    assert len(operations) == 7
    assert operations[0].kind.value == "read"
    for index in (1, 3, 5):
        assert operations[index].kind.value == "write"
        assert operations[index + 1].kind.value == "verify"
        assert operations[index].entity_ids == operations[index + 1].entity_ids


class FailingSequenceTransport(SequenceTransport):
    def __init__(self, state, fail_on_request_index):
        super().__init__(state)
        self.fail_on_request_index = fail_on_request_index

    def send(self, request):
        if len(self.requests) == self.fail_on_request_index:
            self.requests.append(request)
            raise RuntimeError("simulated sequence transport failure")
        return super().send(request)


def test_sequence_failure_stops_at_failed_operation_and_preserves_mutation_context():
    state = {"FIELD_SURFACE": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}}
    transport = FailingSequenceTransport(state, fail_on_request_index=3)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    planner = UnrealTaskPlanner()
    plan = planner.plan_actor_location_sequence(
        UnrealTaskIntent("sequence-failure-1", "fail during second write", ("FIELD_SURFACE",)),
        (
            {"x": 100.0, "y": 200.0, "z": 300.0},
            {"x": 110.0, "y": 210.0, "z": 310.0},
        ),
    )

    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(plan, "sequence-failure-auth")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.operation_index == 3
    assert failure.operation_name == "set_actor_location"
    assert failure.operation_arguments["location"] == {
        "x": 110.0,
        "y": 210.0,
        "z": 310.0,
    }
    assert len(failure.completed_evidence) == 3
    assert len(transport.requests) == 4
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors",
        "set_actor_location",
        "inspect_target_actors",
        "set_actor_location",
    ]
    assert state["FIELD_SURFACE"]["location"] == {
        "x": 100.0,
        "y": 200.0,
        "z": 300.0,
    }
