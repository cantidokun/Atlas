"""Recovery coverage for material and Niagara production domains."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_recovery_sequence import assess_reassessment_sequence, build_reassessment_plan, build_replacement_plan, execute_recovery_sequence, issue_replacement_authorization
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportResponse

ENTITY_ID = "FIELD_SURFACE"


class HeterogeneousRecoveryTransport:
    def __init__(self, fail_operation):
        self.fail_operation = fail_operation
        self.state = {ENTITY_ID: {"entity_id": ENTITY_ID, "actor_name": "FieldSurface", "actor_class": "Actor", "location": {"x": 0.0, "y": 0.0, "z": 0.0}, "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}, "scale": {"x": 1.0, "y": 1.0, "z": 1.0}, "material": {"variant": {"name": "default_surface"}}, "niagara": {"variant": {"name": "none"}}}}
        self.failed = False
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        name = request.operation_name
        if name in {"inspect_target_actors", "inspect_material_state", "inspect_niagara_state", "verify_actor_location", "verify_material_variant", "verify_niagara_variant"}:
            return self._response(request)
        if name == "set_actor_location":
            self.state[ENTITY_ID]["location"] = dict(request.arguments["location"])
            return self._response(request)
        if name == "apply_material_variant":
            if self.fail_operation == name and not self.failed:
                self.failed = True
                return self._response(request, False, "injected material failure")
            self.state[ENTITY_ID]["material"] = {"variant": dict(request.arguments["material_variant"])}
            return self._response(request)
        if name == "apply_niagara_variant":
            if self.fail_operation == name and not self.failed:
                self.failed = True
                return self._response(request, False, "injected Niagara failure")
            self.state[ENTITY_ID]["niagara"] = {"variant": dict(request.arguments["niagara_variant"])}
            return self._response(request)
        return self._response(request, False, f"unsupported operation: {name}")

    def _response(self, request, success=True, error=""):
        return UnrealTransportResponse(request_id=request.request_id, operation_name=request.operation_name, entity_ids=request.entity_ids, success=success, observed_state={ENTITY_ID: dict(self.state[ENTITY_ID])}, error=error, source="heterogeneous-recovery-transport")


def _plan():
    return UnrealTaskPlan("heterogeneous-recovery", (
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", {"entity_ids": (ENTITY_ID,), "location": {"x": 10.0, "y": 20.0, "z": 30.0}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_location", {"entity_ids": (ENTITY_ID,), "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.WRITE, "apply_material_variant", {"entity_ids": (ENTITY_ID,), "material_variant": {"name": "liquid_surface"}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.VERIFY, "verify_material_variant", {"entity_ids": (ENTITY_ID,), "material_variant": {"name": "liquid_surface"}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.WRITE, "apply_niagara_variant", {"entity_ids": (ENTITY_ID,), "niagara_variant": {"name": "goal_burst"}}, (ENTITY_ID,)),
        UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.VERIFY, "verify_niagara_variant", {"entity_ids": (ENTITY_ID,), "niagara_variant": {"name": "goal_burst"}}, (ENTITY_ID,)),
    ))


def _failed_execution(fail_operation):
    transport = HeterogeneousRecoveryTransport(fail_operation)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "heterogeneous-recovery-test"))
    plan = _plan()
    authorization = UnrealPlanAuthorization.issue(plan, "original-auth")
    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute_authorized(plan, authorization)
    return transport, executor, plan, exc_info.value.failure


def test_material_failure_reassesses_mixed_state_and_replaces_only_material():
    transport, executor, plan, failure = _failed_execution("apply_material_variant")
    assert failure.operation_name == "apply_material_variant"
    reassessment = build_reassessment_plan(plan, failure)
    assert [op.name for op in reassessment.operations] == ["inspect_target_actors", "inspect_material_state"]
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "material-reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    assert [step.operation_name for step in assessment.steps] == ["set_actor_location", "apply_material_variant"]
    assert [step.disposition for step in assessment.steps] == ["already_applied", "replacement_required"]
    replacement = build_replacement_plan(plan, assessment)
    assert [op.name for op in replacement.operations] == ["apply_material_variant", "verify_material_variant"]
    assert replacement.operations[0].arguments["material_variant"] == {"name": "liquid_surface"}
    assert replacement.operations[1].arguments["material_variant"] == {"name": "liquid_surface"}
    replacement_auth = issue_replacement_authorization(replacement, "material-replacement-auth")
    result = execute_recovery_sequence(executor, plan, failure, reassessment_auth, replacement_auth)
    assert result.replacement_result is not None
    assert result.replacement_result.success is True
    assert transport.state[ENTITY_ID]["material"]["variant"]["name"] == "liquid_surface"


def test_niagara_failure_reassesses_prior_material_write_and_replaces_only_niagara():
    transport, executor, plan, failure = _failed_execution("apply_niagara_variant")
    assert failure.operation_name == "apply_niagara_variant"
    reassessment = build_reassessment_plan(plan, failure)
    assert [op.name for op in reassessment.operations] == ["inspect_target_actors", "inspect_material_state", "inspect_niagara_state"]
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "niagara-reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    assert [step.disposition for step in assessment.steps] == ["already_applied", "already_applied", "replacement_required"]
    replacement = build_replacement_plan(plan, assessment)
    assert [op.name for op in replacement.operations] == ["apply_niagara_variant", "verify_niagara_variant"]
    assert replacement.operations[0].arguments["niagara_variant"] == {"name": "goal_burst"}
    assert replacement.operations[1].arguments["niagara_variant"] == {"name": "goal_burst"}
    replacement_auth = issue_replacement_authorization(replacement, "niagara-replacement-auth")
    result = execute_recovery_sequence(executor, plan, failure, reassessment_auth, replacement_auth)
    assert result.replacement_result is not None
    assert result.replacement_result.success is True
    assert transport.state[ENTITY_ID]["material"]["variant"]["name"] == "liquid_surface"
    assert transport.state[ENTITY_ID]["niagara"]["variant"]["name"] == "goal_burst"
