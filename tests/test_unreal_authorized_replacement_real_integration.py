"""Live Unreal proof for recovery-to-explicit-replacement authorization."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_reassessment_decision import UnrealReassessmentOutcome
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
        description="integration test authorized replacement actor location",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


def _post_write_failure(intent_id, target_location):
    from planning.unreal_evidence_contract import UnrealEvidence
    from planning.unreal_plan_executor import UnrealPlanExecutionFailure
    return UnrealPlanExecutionFailure(
        intent_id=intent_id,
        operation_index=2,
        operation_name="set_actor_location",
        completed_evidence=(
            UnrealEvidence(
                "inspect_target_actors",
                (ENTITY_ID,),
                {ENTITY_ID: {"entity_id": ENTITY_ID, "location": dict(target_location)}},
                "real-authorized-replacement-test",
                False,
            ),
        ),
        error="simulated post-write failure",
        operation_entity_ids=(ENTITY_ID,),
        operation_arguments={"entity_ids": (ENTITY_ID,), "location": dict(target_location)},
        completed_operation_arguments=({"entity_ids": (ENTITY_ID,)},),
    )


class FailOnceAfterSecondWriteTransport:
    """Real transport that loses the second write response exactly once."""

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


def test_real_unreal_recovery_to_explicit_authorized_replacement():
    """Prove recovery can inform a replacement without authorizing it itself."""
    transport = None
    try:
        transport = FailOnceAfterSecondWriteTransport()
        adapter = UnrealAdapterProduction(
            transport,
            "authorized-replacement-integration",
        )
        executor = UnrealPlanExecutor(adapter)
        coordinator = UnrealRecoveryCoordinator(executor)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            planner.plan_inspection(_intent("replacement-original-read")),
            "replacement-original-read-auth",
        )
        original_location = _location(original_result.evidence_ledger[0])

        first_location = {
            "x": float(original_location["x"]) + 20.0,
            "y": float(original_location["y"]) + 15.0,
            "z": float(original_location["z"]) + 5.0,
        }
        failed_location = {
            "x": float(original_location["x"]) - 25.0,
            "y": float(original_location["y"]) + 25.0,
            "z": float(original_location["z"]) + 10.0,
        }
        replacement_location = {
            "x": float(original_location["x"]) + 35.0,
            "y": float(original_location["y"]) - 20.0,
            "z": float(original_location["z"]) + 12.0,
        }

        try:
            failed_plan = planner.plan_actor_location_sequence(
                _intent("replacement-failed-sequence"),
                (first_location, failed_location),
            )

            with pytest.raises(UnrealPlanExecutionError) as exc_info:
                executor.execute(failed_plan, "replacement-failed-sequence-auth")

            failure = exc_info.value.failure
            assert failure is not None
            assert failure.operation_index == 3
            assert failure.operation_name == "set_actor_location"

            reassessment = coordinator.reassess(
                failure,
                "replacement-reassessment-auth",
            )
            assert reassessment.decision is not None
            assert reassessment.decision.outcome is UnrealReassessmentOutcome.CONFIRMED
            assert reassessment.decision.retry_authorized is False
            assert reassessment.decision.mutation_authorized is False
            assert reassessment.execution_result is not None
            assert _location(reassessment.execution_result.evidence_ledger[0]) == pytest.approx(
                failed_location
            )

            replacement_plan = planner.plan_actor_location_write(
                _intent("replacement-authorized-plan"),
                replacement_location,
            )
            assert replacement_plan != failed_plan

            authorization = UnrealPlanAuthorization.issue(
                replacement_plan,
                "replacement-authorized-auth",
            )

            changed_plan = planner.plan_actor_location_write(
                _intent("replacement-authorized-plan"),
                {
                    "x": replacement_location["x"] + 1.0,
                    "y": replacement_location["y"],
                    "z": replacement_location["z"],
                },
            )
            request_count_before_rejection = len(transport.requests)
            with pytest.raises(
                UnrealPlanExecutionError,
                match="does not match the exact Unreal task plan",
            ):
                executor.execute_authorized(changed_plan, authorization)
            assert len(transport.requests) == request_count_before_rejection

            replacement_result = executor.execute_authorized(
                replacement_plan,
                authorization,
            )
            assert replacement_result.success is True
            assert len(replacement_result.evidence_ledger) == 3
            assert replacement_result.evidence_ledger[2].operation_name == "verify_actor_location"
            assert _location(replacement_result.evidence_ledger[2]) == pytest.approx(
                replacement_location
            )

            replacement_requests = transport.requests[request_count_before_rejection:]
            assert [request.operation_name for request in replacement_requests] == [
                "inspect_target_actors",
                "set_actor_location",
                "inspect_target_actors",
            ]
            assert all(
                request.authorization_id == "replacement-authorized-auth"
                for request in replacement_requests
            )

        finally:
            restore_result = executor.execute(
                planner.plan_actor_location_write(
                    _intent("replacement-restore"),
                    original_location,
                ),
                "replacement-restore-auth",
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
