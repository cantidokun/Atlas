from dataclasses import dataclass

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportResponse


@dataclass
class RecordingTransport:
    response_state: dict

    def __post_init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=self.response_state,
            error="",
            source="test-unreal",
        )


def _location_operation(location):
    return UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",), "location": location},
        entity_ids=("FIELD_SURFACE",),
    )


def _verify_operation(expected=None):
    expected = {"x": 10.0, "y": 20.0, "z": 30.0} if expected is None else expected
    return UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",), "expected_location": expected},
        entity_ids=("FIELD_SURFACE",),
    )


def test_executor_preserves_actor_location_payload():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 1, "y": 2, "z": 3}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    target = {"x": 1.0, "y": 2.0, "z": 3.0}
    plan = UnrealTaskPlan("location-write", (_location_operation(target), _verify_operation(target)))

    result = executor.execute(plan, "auth-location-001")

    assert result.success is True
    assert transport.requests[0].arguments["location"] == target
    assert transport.requests[0].authorization_id == "auth-location-001"


def test_executor_rejects_malformed_actor_location_before_transport():
    transport = RecordingTransport({})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write", (_location_operation({"x": 1.0, "y": 2.0}), _verify_operation()))

    with pytest.raises(UnrealPlanExecutionError, match="location must contain exactly x, y, and z"):
        executor.execute(plan, "auth-location-002")

    assert transport.requests == []


def test_executor_rejects_unverified_write():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 1, "y": 2, "z": 3}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write-unverified", (_location_operation({"x": 1.0, "y": 2.0, "z": 3.0}),))

    with pytest.raises(UnrealPlanExecutionError, match="must be followed by verification"):
        executor.execute(plan, "auth-location-003")

    assert transport.requests == []


def test_executor_rejects_write_with_wrong_verification_targets():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 10, "y": 20, "z": 30}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    wrong_target_verify = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_actor_location",
        arguments={"entity_ids": ("OTHER_ACTOR",), "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0}},
        entity_ids=("OTHER_ACTOR",),
    )
    plan = UnrealTaskPlan("location-write-wrong-target", (_location_operation({"x": 10.0, "y": 20.0, "z": 30.0}), wrong_target_verify))

    with pytest.raises(UnrealPlanExecutionError, match="must target the same entities"):
        executor.execute(plan, "auth-location-004")

    assert transport.requests == []


def test_executor_rejects_semantically_wrong_verifier_before_transport():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 10, "y": 20, "z": 30}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    wrong_verifier = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_actor_scale",
        arguments={"entity_ids": ("FIELD_SURFACE",), "expected_scale": {"x": 1.0, "y": 1.0, "z": 1.0}},
        entity_ids=("FIELD_SURFACE",),
    )
    plan = UnrealTaskPlan("location-write-wrong-verifier", (_location_operation({"x": 10.0, "y": 20.0, "z": 30.0}), wrong_verifier))

    with pytest.raises(UnrealPlanExecutionError, match="must be followed by 'verify_actor_location'"):
        executor.execute(plan, "auth-location-010")

    assert transport.requests == []


def test_executor_verifies_actor_location_after_write():
    target = {"x": 10.0, "y": 20.0, "z": 30.0}
    transport = RecordingTransport({"FIELD_SURFACE": {"location": target}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write-verify", (_location_operation(target), _verify_operation(target)))

    result = executor.execute(plan, "auth-location-005")

    assert result.success is True
    assert len(result.evidence_ledger) == 2
    assert [e.operation_name for e in result.evidence_ledger] == ["set_actor_location", "verify_actor_location"]
    assert [request.operation_name for request in transport.requests] == ["set_actor_location", "inspect_target_actors"]
    assert result.evidence_ledger[1].verified is True


def test_executor_rejects_post_write_location_mismatch():
    requested = {"x": 10.0, "y": 20.0, "z": 30.0}
    observed = {"x": 10.0, "y": 20.5, "z": 30.0}
    transport = RecordingTransport({"FIELD_SURFACE": {"location": observed}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write-mismatch", (_location_operation(requested), _verify_operation(requested)))

    with pytest.raises(UnrealPlanExecutionError, match="does not match expected"):
        executor.execute(plan, "auth-location-006")

    assert len(transport.requests) == 2


def test_executor_failure_preserves_completed_evidence_and_boundary():
    requested = {"x": 10.0, "y": 20.0, "z": 30.0}
    observed = {"x": 10.0, "y": 20.5, "z": 30.0}
    transport = RecordingTransport({"FIELD_SURFACE": {"location": observed}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan(
        "location-write-failure-context",
        (
            UnrealOperation(capability=UnrealCapability.INSPECT_ACTOR, kind=UnrealOperationKind.READ, name="inspect_target_actors", arguments={"entity_ids": ("FIELD_SURFACE",)}, entity_ids=("FIELD_SURFACE",)),
            _location_operation(requested),
            _verify_operation(requested),
        ),
    )

    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(plan, "auth-location-007")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.intent_id == "location-write-failure-context"
    assert failure.operation_index == 2
    assert failure.operation_name == "verify_actor_location"
    assert failure.operation_entity_ids == ("FIELD_SURFACE",)
    assert failure.operation_arguments == {"entity_ids": ("FIELD_SURFACE",), "expected_location": requested}
    assert len(failure.completed_evidence) == 2
    assert failure.completed_evidence[0].operation_name == "inspect_target_actors"
    assert failure.completed_evidence[1].operation_name == "set_actor_location"
    assert failure.completed_operation_arguments == (
        {"entity_ids": ("FIELD_SURFACE",)},
        {"entity_ids": ("FIELD_SURFACE",), "location": requested},
    )
    assert "does not match expected" in failure.error


def test_executor_failure_context_preserves_mutation_intent_for_post_write_recovery():
    requested = {"x": 15.0, "y": 25.0, "z": 35.0}
    observed = {"x": 15.0, "y": 25.5, "z": 35.0}
    transport = RecordingTransport({"FIELD_SURFACE": {"location": observed}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write-recovery-intent", (_location_operation(requested), _verify_operation(requested)))

    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(plan, "auth-location-009")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.operation_name == "verify_actor_location"
    assert failure.completed_operation_arguments[-1]["location"] == requested


class FailingTransport:
    def __init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        raise UnrealAdapterError("simulated Unreal write failure")


def test_executor_failure_preserves_operation_targets_without_completed_evidence():
    transport = FailingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write-no-evidence", (_location_operation({"x": 1.0, "y": 2.0, "z": 3.0}), _verify_operation({"x": 1.0, "y": 2.0, "z": 3.0})))

    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(plan, "auth-location-008")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.operation_name == "set_actor_location"
    assert failure.operation_entity_ids == ("FIELD_SURFACE",)
    assert failure.operation_arguments == {"entity_ids": ("FIELD_SURFACE",), "location": {"x": 1.0, "y": 2.0, "z": 3.0}}
    assert failure.completed_operation_arguments == ()
    assert failure.completed_evidence == ()


class UnexpectedFailureTransport:
    def __init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        raise RuntimeError("simulated unexpected transport runtime failure")


def test_executor_wraps_unexpected_exception_with_failure_boundary():
    transport = UnexpectedFailureTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("unexpected-failure-context", (_location_operation({"x": 4.0, "y": 5.0, "z": 6.0}), _verify_operation({"x": 4.0, "y": 5.0, "z": 6.0})))

    with pytest.raises(UnrealPlanExecutionError, match="Unexpected execution failure") as exc_info:
        executor.execute(plan, "auth-unexpected-001")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.operation_index == 0
    assert failure.operation_name == "set_actor_location"
    assert failure.operation_entity_ids == ("FIELD_SURFACE",)
    assert failure.operation_arguments == {"entity_ids": ("FIELD_SURFACE",), "location": {"x": 4.0, "y": 5.0, "z": 6.0}}
    assert failure.completed_evidence == ()
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_executor_preflights_entire_plan_before_any_transport_mutation():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 10, "y": 20, "z": 30}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    malformed_scale = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_scale",
        arguments={"entity_ids": ("FIELD_SURFACE",), "scale": {"x": 1.1, "y": 1.1}},
        entity_ids=("FIELD_SURFACE",),
    )
    plan = UnrealTaskPlan(
        "preflight-later-operation",
        (
            UnrealOperation(capability=UnrealCapability.INSPECT_ACTOR, kind=UnrealOperationKind.READ, name="inspect_target_actors", arguments={"entity_ids": ("FIELD_SURFACE",)}, entity_ids=("FIELD_SURFACE",)),
            _location_operation({"x": 10.0, "y": 20.0, "z": 30.0}),
            _verify_operation({"x": 10.0, "y": 20.0, "z": 30.0}),
            malformed_scale,
            UnrealOperation(capability=UnrealCapability.MODIFY_ACTOR, kind=UnrealOperationKind.VERIFY, name="verify_actor_scale", arguments={"entity_ids": ("FIELD_SURFACE",), "expected_scale": {"x": 1.1, "y": 1.1, "z": 1.1}}, entity_ids=("FIELD_SURFACE",)),
        ),
    )

    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        executor.execute(plan, "auth-preflight-001")

    assert transport.requests == []
