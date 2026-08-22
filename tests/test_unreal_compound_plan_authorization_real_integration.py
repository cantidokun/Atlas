"""Live Unreal proof for plan-bound authorization of compound plans."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError, create_named_pipe_transport


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


class RecordingTransport:
    """Capture real transport requests while delegating to the named pipe."""

    def __init__(self, transport):
        self._transport = transport
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return self._transport.send(request)


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="integration test compound authorization",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


def test_real_unreal_compound_plan_requires_exact_authorization_and_restores():
    """Prove an authorized compound plan is the only compound mutation accepted."""
    transport = None
    planner = UnrealTaskPlanner()
    try:
        transport = RecordingTransport(create_named_pipe_transport())
        adapter = UnrealAdapterProduction(transport, "compound-authorization-integration")
        executor = UnrealPlanExecutor(adapter)

        original = executor.execute(
            planner.plan_inspection(_intent("compound-auth-original-read")),
            "compound-auth-original-read",
        )
        original_location = _location(original.evidence_ledger[0])

        target_location = {
            "x": float(original_location["x"]) + 16.0,
            "y": float(original_location["y"]) - 11.0,
            "z": float(original_location["z"]) + 6.0,
        }
        changed_location = dict(target_location)
        changed_location["x"] += 1.0

        intent = _intent("compound-auth-live")
        authorized_plan = planner.compose_plans(
            intent,
            (
                planner.plan_inspection(intent),
                planner.plan_actor_location_write(intent, target_location),
            ),
        )
        changed_plan = planner.compose_plans(
            intent,
            (
                planner.plan_inspection(intent),
                planner.plan_actor_location_write(intent, changed_location),
            ),
        )
        authorization = UnrealPlanAuthorization.issue(
            authorized_plan,
            "compound-authorized-live-auth",
        )

        before_rejection = len(transport.requests)
        with pytest.raises(
            UnrealPlanExecutionError,
            match="does not match the exact Unreal task plan",
        ):
            executor.execute_authorized(changed_plan, authorization)
        assert len(transport.requests) == before_rejection

        result = executor.execute_authorized(authorized_plan, authorization)

        assert result.success is True
        assert len(result.evidence_ledger) == 5
        assert [evidence.operation_name for evidence in result.evidence_ledger] == [
            "inspect_target_actors",
            "verify_target_actor_mapping",
            "inspect_target_actors",
            "set_actor_location",
            "verify_target_actor_mapping",
        ]
        assert _location(result.evidence_ledger[2]) == pytest.approx(original_location)
        assert _location(result.evidence_ledger[3]) == pytest.approx(target_location)
        assert _location(result.evidence_ledger[4]) == pytest.approx(target_location)

        authorized_requests = transport.requests[before_rejection:]
        assert [request.operation_name for request in authorized_requests] == [
            "inspect_target_actors",
            "inspect_target_actors",
            "inspect_target_actors",
            "set_actor_location",
            "inspect_target_actors",
        ]
        assert all(
            request.authorization_id == "compound-authorized-live-auth"
            for request in authorized_requests
        )

    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        message = str(exc).lower()
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "actor not found" in message or "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
    finally:
        if transport is not None and "original_location" in locals():
            restore_adapter = UnrealAdapterProduction(transport, "compound-authorization-restore")
            restore_executor = UnrealPlanExecutor(restore_adapter)
            try:
                restore_executor.execute(
                    planner.plan_actor_location_write(
                        _intent("compound-auth-restore"),
                        original_location,
                    ),
                    "compound-authorized-restore-auth",
                )
            except (UnrealAdapterError, NamedPipeTransportError):
                pass
