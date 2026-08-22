"""Regression coverage for named-pipe failures crossing the production adapter."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportRequest
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportDisconnectedError,
    NamedPipeTransportTimeoutError,
)


class FailingTransport:
    def __init__(self, error):
        self.error = error
        self.requests = []

    def send(self, request: UnrealTransportRequest):
        self.requests.append(request)
        raise self.error


def _operation():
    return UnrealOperation(
        name="inspect_target_actors",
        capability=UnrealCapability.INSPECT_ACTOR,
        kind=UnrealOperationKind.READ,
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
    )


@pytest.mark.parametrize(
    "transport_error",
    [
        NamedPipeTransportTimeoutError("read timed out"),
        NamedPipeTransportDisconnectedError("server disconnected"),
    ],
)
def test_transport_failures_are_wrapped_at_adapter_boundary(transport_error):
    adapter = UnrealAdapterProduction(FailingTransport(transport_error), source_tag="test")

    with pytest.raises(UnrealAdapterError, match="Unreal transport failed") as exc_info:
        adapter.inspect(_operation(), "auth-transport-failure")

    assert exc_info.value.__cause__ is transport_error


def test_transport_failure_reaches_executor_failure_boundary_with_context():
    transport_error = NamedPipeTransportDisconnectedError("server disconnected")
    adapter = UnrealAdapterProduction(FailingTransport(transport_error), source_tag="test")
    executor = UnrealPlanExecutor(adapter)
    plan = UnrealTaskPlanner().plan_inspection(
        UnrealTaskIntent(
            intent_id="transport-failure-boundary",
            description="test transport failure boundary",
            target_entity_ids=("FIELD_SURFACE",),
        )
    )

    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(plan, "auth-transport-failure")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.operation_index == 0
    assert failure.operation_name == "inspect_target_actors"
    assert "disconnected" in failure.error
    assert failure.operation_entity_ids == ("FIELD_SURFACE",)
