"""Real Unreal integration coverage for partial sequence failure recovery."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_recovery_coordinator import UnrealRecoveryCoordinator
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportError,
    create_named_pipe_transport,
)


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="integration test partial actor location recovery",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


class FailOnceAfterSecondWriteTransport:
    """Real named-pipe transport with one deterministic post-write fault.

    The second location write is delivered to Unreal successfully, then its
    response is discarded and a transport failure is raised. Subsequent
    requests use the same real transport, allowing recovery to obtain fresh
    state without retrying the write.
    """

    def __init__(self):
        self._transport = create_named_pipe_transport()
        self.write_count = 0
        self.failed = False
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        response = self._transport.send(request)
        if request.operation_name == "set_actor_location":
            self.write_count += 1
            if self.write_count == 2 and not self.failed:
                self.failed = True
                raise NamedPipeTransportError(
                    "injected post-write failure after Unreal accepted the second location write"
                )
        return response


def test_real_unreal_partial_sequence_failure_reassesses_without_retrying_write():
    """Prove the live partial-failure/recovery boundary against Unreal.

    The second WRITE is delivered to the real Unreal Editor, but the transport
    response is deliberately discarded. The executor must stop at that exact
    operation. Recovery then performs one fresh READ only; it must not replay
    the failed WRITE. The actor is restored to its original location in cleanup.
    """
    transport = None
    try:
        transport = FailOnceAfterSecondWriteTransport()
        adapter = UnrealAdapterProduction(
            transport,
            "partial-sequence-recovery-integration",
        )
        executor = UnrealPlanExecutor(adapter)
        coordinator = UnrealRecoveryCoordinator(executor)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            planner.plan_inspection(_intent("real-partial-original")),
            "real-partial-original-auth",
        )
        original_location = _location(original_result.evidence_ledger[0])

        first_location = {
            "x": float(original_location["x"]) + 20.0,
            "y": float(original_location["y"]) + 15.0,
            "z": float(original_location["z"]) + 5.0,
        }
        second_location = {
            "x": float(original_location["x"]) - 25.0,
            "y": float(original_location["y"]) + 25.0,
            "z": float(original_location["z"]) + 10.0,
        }

        try:
            plan = planner.plan_actor_location_sequence(
                _intent("real-partial-sequence"),
                (first_location, second_location),
            )

            with pytest.raises(UnrealPlanExecutionError) as exc_info:
                executor.execute(plan, "real-partial-sequence-auth")

            failure = exc_info.value.failure
            assert failure is not None
            assert failure.operation_index == 3
            assert failure.operation_name == "set_actor_location"
            assert failure.operation_arguments["location"] == second_location
            assert len(failure.completed_evidence) == 3
            assert [request.operation_name for request in transport.requests] == [
                "inspect_target_actors",
                "set_actor_location",
                "inspect_target_actors",
                "set_actor_location",
            ]

            reassessment = coordinator.reassess(
                failure,
                "real-partial-reassessment-auth",
            )

            assert reassessment.decision is not None
            assert reassessment.decision.retry_authorized is False
            assert reassessment.decision.mutation_authorized is False
            assert reassessment.execution_result is not None
            assert [
                evidence.operation_name
                for evidence in reassessment.execution_result.evidence_ledger
            ] == ["inspect_target_actors"]
            assert _location(
                reassessment.execution_result.evidence_ledger[0]
            ) == pytest.approx(second_location)
            assert [request.operation_name for request in transport.requests] == [
                "inspect_target_actors",
                "set_actor_location",
                "inspect_target_actors",
                "set_actor_location",
                "inspect_target_actors",
            ]
            assert transport.write_count == 2

        finally:
            restore_result = executor.execute(
                planner.plan_actor_location_write(
                    _intent("real-partial-restore"),
                    original_location,
                ),
                "real-partial-restore-auth",
            )
            assert restore_result.success is True
            assert _location(restore_result.evidence_ledger[2]) == pytest.approx(
                original_location
            )

    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        message = str(exc).lower()
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "actor not found" in message or "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
