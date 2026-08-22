"""Live Unreal proof for deterministic compound task-plan composition."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportError,
    create_named_pipe_transport,
)


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
        description="integration test compound inspection and actor location plan",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


def test_real_unreal_compound_plan_executes_subplans_in_order_and_restores():
    """Prove composed sub-plans execute deterministically against real Unreal."""
    transport = None
    try:
        transport = RecordingTransport(create_named_pipe_transport())
        adapter = UnrealAdapterProduction(transport, "compound-plan-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original = executor.execute(
            planner.plan_inspection(_intent("compound-original-read")),
            "compound-original-read-auth",
        )
        original_location = _location(original.evidence_ledger[0])

        target_location = {
            "x": float(original_location["x"]) + 18.0,
            "y": float(original_location["y"]) - 12.0,
            "z": float(original_location["z"]) + 7.0,
        }

        intent = _intent("compound-live")
        composed = planner.compose_plans(
            intent,
            (
                planner.plan_inspection(intent),
                planner.plan_actor_location_write(intent, target_location),
            ),
        )

        result = executor.execute(composed, "compound-live-auth")

        assert result.success is True
        assert len(result.evidence_ledger) == 5
        assert [evidence.operation_name for evidence in result.evidence_ledger] == [
            "inspect_target_actors",
            "verify_target_actor_mapping",
            "inspect_target_actors",
            "set_actor_location",
            "verify_target_actor_mapping",
        ]
        # The first two evidence entries belong to the inspection sub-plan.
        # The location-write sub-plan then contributes its pre-write read,
        # mutation, and post-write verification in that exact order.
        assert _location(result.evidence_ledger[2]) == pytest.approx(original_location)
        assert _location(result.evidence_ledger[3]) == pytest.approx(target_location)
        assert _location(result.evidence_ledger[4]) == pytest.approx(target_location)

        assert [request.operation_name for request in transport.requests[-5:]] == [
            "inspect_target_actors",
            "inspect_target_actors",
            "inspect_target_actors",
            "set_actor_location",
            "inspect_target_actors",
        ]
        assert all(
            request.authorization_id == "compound-live-auth"
            for request in transport.requests[-5:]
        )

    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        message = str(exc).lower()
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "actor not found" in message or "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
    finally:
        if transport is not None:
            restore_adapter = UnrealAdapterProduction(transport, "compound-plan-restore")
            restore_executor = UnrealPlanExecutor(restore_adapter)
            try:
                restore_intent = _intent("compound-restore")
                # The fixture's original location is only available after the
                # initial read. If setup failed before that read, there is no
                # mutation to restore.
                if "original_location" in locals():
                    restore_executor.execute(
                        planner.plan_actor_location_write(
                            restore_intent,
                            original_location,
                        ),
                        "compound-restore-auth",
                    )
            except (UnrealAdapterError, NamedPipeTransportError):
                # Preserve the primary test failure; cleanup failures are
                # surfaced by the existing dedicated location integration gate.
                pass
