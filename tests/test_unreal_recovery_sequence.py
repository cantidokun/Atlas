from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_recovery_sequence import UnrealRecoverySequenceAssessment, assess_reassessment_sequence, build_reassessment_plan, build_replacement_plan, execute_replacement_authorized, issue_replacement_authorization
from planning.unreal_task_planner import UnrealTaskPlan


class NoTransport:
    def send(self, request):
        raise AssertionError("transport must not be reached for stale authorization")


def _plan():
    entity_ids = ("FIELD_SURFACE",)
    return UnrealTaskPlan("composite-live", (
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", {"entity_ids": entity_ids, "location": {"x": 10.0, "y": 20.0, "z": 30.0}}, entity_ids),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_location", {"entity_ids": entity_ids, "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0}}, entity_ids),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_rotation", {"entity_ids": entity_ids, "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}}, entity_ids),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_rotation", {"entity_ids": entity_ids, "expected_rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}}, entity_ids),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_scale", {"entity_ids": entity_ids, "scale": {"x": 1.1, "y": 1.1, "z": 1.1}}, entity_ids),
        UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_scale", {"entity_ids": entity_ids, "expected_scale": {"x": 1.1, "y": 1.1, "z": 1.1}}, entity_ids),
        UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.READ, "inspect_material_state", {"entity_ids": entity_ids}, entity_ids),
        UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.WRITE, "apply_material_variant", {"entity_ids": entity_ids, "material_variant": {"name": "liquid_surface"}}, entity_ids),
        UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.VERIFY, "verify_material_variant", {"entity_ids": entity_ids, "material_variant": {"name": "liquid_surface"}}, entity_ids),
        UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.READ, "inspect_niagara_state", {"entity_ids": entity_ids}, entity_ids),
        UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.WRITE, "apply_niagara_variant", {"entity_ids": entity_ids, "niagara_variant": {"name": "goal_burst"}}, entity_ids),
        UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.VERIFY, "verify_niagara_variant", {"entity_ids": entity_ids, "niagara_variant": {"name": "goal_burst"}}, entity_ids),
    ))


def _failure():
    return UnrealPlanExecutionFailure("composite-live", 8, "verify_material_variant", (), "verification failed", ("FIELD_SURFACE",), {"entity_ids": ("FIELD_SURFACE",), "material_variant": {"name": "liquid_surface"}}, ())


def _actor_evidence():
    return UnrealEvidence("inspect_target_actors", ("FIELD_SURFACE",), {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "actor_name": "FieldSurface", "actor_class": "Actor", "location": {"x": 10.0, "y": 20.0, "z": 30.0}, "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}, "scale": {"x": 1.1, "y": 1.1, "z": 1.1}}}, "unreal-editor-atlas-transport")


def _material_evidence():
    return UnrealEvidence("inspect_material_state", ("FIELD_SURFACE",), {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "wet_surface"}}}}, "unreal-editor-atlas-transport")


def test_reassessment_plan_uses_one_read_per_state_domain():
    reassessment = build_reassessment_plan(_plan(), _failure())
    assert [operation.name for operation in reassessment.operations] == ["inspect_target_actors", "inspect_material_state"]
    assert [operation.capability for operation in reassessment.operations] == [UnrealCapability.MODIFY_ACTOR, UnrealCapability.MATERIAL]
    assert all(operation.kind is UnrealOperationKind.READ for operation in reassessment.operations)


def test_sequence_assessment_classifies_transform_and_material_domains_independently():
    result = UnrealPlanExecutionResult("composite-live:reassess-sequence", (_actor_evidence(), _material_evidence()), True)
    assessment = assess_reassessment_sequence(_plan(), _failure(), result)
    assert assessment.disposition == "replacement_required"
    by_name = {step.operation_name: step for step in assessment.steps}
    assert by_name["set_actor_location"].disposition == "already_applied"
    assert by_name["set_actor_rotation"].disposition == "already_applied"
    assert by_name["set_actor_scale"].disposition == "already_applied"
    assert by_name["apply_material_variant"].disposition == "replacement_required"


def _assessment_for_material():
    return UnrealRecoverySequenceAssessment(tuple(
        type("Step", (), {"operation_index": index, "operation_name": name, "entity_ids": ("FIELD_SURFACE",), "disposition": disposition, "reason": "fresh state classification"})()
        for index, name, disposition in (
            (0, "set_actor_location", "already_applied"),
            (2, "set_actor_rotation", "already_applied"),
            (4, "set_actor_scale", "already_applied"),
            (7, "apply_material_variant", "replacement_required"),
        )
    ))


def test_sequence_replacement_rebuilds_only_mismatched_material_domain():
    replacement = build_replacement_plan(_plan(), _assessment_for_material())
    assert [operation.name for operation in replacement.operations] == ["apply_material_variant", "verify_material_variant"]
    assert replacement.operations[0].arguments["material_variant"] == {"name": "liquid_surface"}


def test_sequence_replacement_requires_new_authorization():
    replacement = build_replacement_plan(_plan(), _assessment_for_material())
    receipt = issue_replacement_authorization(replacement, "material-recovery-auth")
    assert receipt.matches(replacement)
    stale = UnrealPlanAuthorization.issue(build_reassessment_plan(_plan(), _failure()), "stale-reassessment-auth")
    executor = UnrealPlanExecutor(UnrealAdapterProduction(NoTransport()))
    try:
        execute_replacement_authorized(executor, replacement, stale)
    except UnrealPlanExecutionError as exc:
        assert str(exc) == "authorization receipt does not match the exact Unreal task plan"
    else:
        raise AssertionError("stale reassessment authorization must not reach transport")
