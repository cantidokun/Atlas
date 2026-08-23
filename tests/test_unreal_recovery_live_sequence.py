"""Deterministic end-to-end recovery gate using the production executor and adapter."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_recovery_sequence import (
    assess_reassessment_sequence,
    build_reassessment_plan,
    build_replacement_plan,
    execute_recovery_sequence,
    issue_replacement_authorization,
    execute_replacement_authorized,
)
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportResponse


ENTITY_ID = "FIELD_SURFACE"


class StatefulRecoveryTransport:
    def __init__(self):
        self.state = {
            ENTITY_ID: {
                "entity_id": ENTITY_ID,
                "actor_name": "FieldSurface",
                "actor_class": "Actor",
                "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            }
        }
        self.fail_rotation_once = True
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        if request.operation_name == "inspect_target_actors":
            return self._response(request, True)
        if request.operation_name == "set_actor_location":
            self.state[ENTITY_ID]["location"] = dict(request.arguments["location"])
            return self._response(request, True)
        if request.operation_name == "set_actor_rotation":
            if self.fail_rotation_once:
                self.fail_rotation_once = False
                return self._response(request, False, "deterministic injected rotation failure")
            self.state[ENTITY_ID]["rotation"] = dict(request.arguments["rotation"])
            return self._response(request, True)
        if request.operation_name in {"verify_actor_location", "verify_actor_rotation", "verify_target_actor_mapping"}:
            return self._response(request, True)
        return self._response(request, False, f"unsupported fixture operation: {request.operation_name}")

    def _response(self, request, success, error=""):
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=success,
            observed_state={ENTITY_ID: dict(self.state[ENTITY_ID])},
            error=error,
            source="deterministic-recovery-transport",
        )


def _plan():
    return UnrealTaskPlan("composite-live-recovery", (
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", {"entity_ids": (ENTITY_ID,), "location": {"x": 10.0, "y": 20.0, "z": 30.0}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_location", {"entity_ids": (ENTITY_ID,), "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_rotation", {"entity_ids": (ENTITY_ID,), "rotation": {"pitch": 0.0, "yaw": 45.0, "roll": 0.0}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_rotation", {"entity_ids": (ENTITY_ID,), "expected_rotation": {"pitch": 0.0, "yaw": 45.0, "roll": 0.0}}, (ENTITY_ID,)),
    ))


def _failed_execution():
    transport = StatefulRecoveryTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "recovery-sequence-test"))
    plan = _plan()
    authorization = UnrealPlanAuthorization.issue(plan, "composite-original-auth")
    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute_authorized(plan, authorization)
    return transport, executor, plan, exc_info.value.failure


def test_production_executor_recovery_sequence_replaces_only_failed_write():
    transport, executor, plan, failure = _failed_execution()
    assert failure is not None
    assert failure.operation_index == 2
    assert failure.operation_name == "set_actor_rotation"
    assert transport.state[ENTITY_ID]["location"] == {"x": 10.0, "y": 20.0, "z": 30.0}
    assert transport.state[ENTITY_ID]["rotation"] == {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}

    reassessment = build_reassessment_plan(plan, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    assert [step.operation_name for step in assessment.steps] == ["set_actor_location", "set_actor_rotation"]
    assert [step.disposition for step in assessment.steps] == ["already_applied", "replacement_required"]

    replacement = build_replacement_plan(plan, assessment)
    assert [operation.name for operation in replacement.operations] == ["set_actor_rotation", "verify_actor_rotation"]
    replacement_auth = issue_replacement_authorization(replacement, "replacement-auth")
    result = execute_replacement_authorized(executor, replacement, replacement_auth)
    assert result.success is True
    assert [e.operation_name for e in result.evidence_ledger] == ["set_actor_rotation", "verify_actor_rotation"]
    assert result.evidence_ledger[-1].verified is True
    assert transport.state[ENTITY_ID]["location"] == {"x": 10.0, "y": 20.0, "z": 30.0}
    assert transport.state[ENTITY_ID]["rotation"] == {"pitch": 0.0, "yaw": 45.0, "roll": 0.0}
    assert transport.requests[-2].authorization_id == "replacement-auth"
    assert transport.requests[-1].authorization_id == "replacement-auth"


def test_recovery_coordinator_requires_replacement_authorization_before_any_replacement_write():
    transport, executor, plan, failure = _failed_execution()
    reassessment = build_reassessment_plan(plan, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    baseline = len(transport.requests)

    with pytest.raises(ValueError, match="separate replacement authorization"):
        execute_recovery_sequence(executor, plan, failure, reassessment_auth)

    assert [request.operation_name for request in transport.requests[baseline:]] == ["inspect_target_actors"]
    assert all(request.operation_name != "set_actor_rotation" for request in transport.requests[baseline:])


def test_recovery_coordinator_executes_only_the_new_authorized_replacement_plan():
    transport, executor, plan, failure = _failed_execution()
    reassessment = build_reassessment_plan(plan, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    replacement = build_replacement_plan(plan, assessment)
    replacement_auth = issue_replacement_authorization(replacement, "replacement-auth")

    result = execute_recovery_sequence(executor, plan, failure, reassessment_auth, replacement_auth)
    assert result.assessment.disposition == "replacement_required"
    assert result.replacement_plan == replacement
    assert result.replacement_result is not None
    assert result.replacement_result.success is True
    assert transport.state[ENTITY_ID]["rotation"] == {"pitch": 0.0, "yaw": 45.0, "roll": 0.0}
    assert transport.requests[-2].authorization_id == "replacement-auth"
    assert transport.requests[-1].authorization_id == "replacement-auth"
