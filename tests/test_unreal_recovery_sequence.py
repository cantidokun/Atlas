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


def _composite_plan():
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


def _failure_at(index, name):
    return UnrealPlanExecutionFailure(
        intent_id="composite-live",
        operation_index=index,
        operation_name=name,
        completed_evidence=(),
        error="verification failed",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={"entity_ids": ("FIELD_SURFACE",)},
    )


def _actor_evidence(location=(10.0,20.0,30.0), rotation=(0.0,0.0,0.0), scale=(1.0,1.0,1.0)):
    return UnrealEvidence("inspect_target_actors", ("FIELD_SURFACE",), {"FIELD_SURFACE": {"entity_id":"FIELD_SURFACE","actor_name":"FieldSurface","actor_class":"Actor","location":{"x":location[0],"y":location[1],"z":location[2]},"rotation":{"pitch":rotation[0],"yaw":rotation[1],"roll":rotation[2]},"scale":{"x":scale[0],"y":scale[1],"z":scale[2]}}}, "unreal-editor-atlas-transport")


def _material_evidence(name):
    return UnrealEvidence("inspect_material_state", ("FIELD_SURFACE",), {"FIELD_SURFACE": {"material": {"variant": {"name": name}}}}, "unreal-editor-atlas-transport")


def _niagara_evidence(name):
    return UnrealEvidence("inspect_niagara_state", ("FIELD_SURFACE",), {"FIELD_SURFACE": {"niagara": {"variant": {"name": name}}}}, "unreal-editor-atlas-transport")


def _mixed_assessment():
    return UnrealRecoverySequenceAssessment((
        type("Step", (), {"operation_index": 0, "operation_name": "set_actor_location", "entity_ids": ("FIELD_SURFACE",), "disposition": "already_applied", "reason": "fresh state matches"})(),
        type("Step", (), {"operation_index": 2, "operation_name": "set_actor_rotation", "entity_ids": ("FIELD_SURFACE",), "disposition": "replacement_required", "reason": "fresh state differs"})(),
        type("Step", (), {"operation_index": 4, "operation_name": "set_actor_scale", "entity_ids": ("FIELD_SURFACE",), "disposition": "already_applied", "reason": "fresh state matches"})(),
        type("Step", (), {"operation_index": 7, "operation_name": "apply_material_variant", "entity_ids": ("FIELD_SURFACE",), "disposition": "replacement_required", "reason": "fresh state differs"})(),
        type("Step", (), {"operation_index": 10, "operation_name": "apply_niagara_variant", "entity_ids": ("FIELD_SURFACE",), "disposition": "already_applied", "reason": "fresh state matches"})(),
    ))


def test_reassessment_plan_deduplicates_actor_material_and_niagara_read_domains():
    plan = _composite_plan()
    failure = _failure_at(11, "verify_niagara_variant")
    reassessment = build_reassessment_plan(plan, failure)
    assert [(operation.name, operation.capability) for operation in reassessment.operations] == [
        ("inspect_target_actors", UnrealCapability.MODIFY_ACTOR),
        ("inspect_material_state", UnrealCapability.MATERIAL),
        ("inspect_niagara_state", UnrealCapability.NIAGARA),
    ]
    assert all(operation.kind is UnrealOperationKind.READ for operation in reassessment.operations)


def test_sequence_assessment_supports_mixed_actor_material_and_niagara_dispositions():
    plan = _composite_plan()
    failure = _failure_at(11, "verify_niagara_variant")
    result = UnrealPlanExecutionResult(
        "composite-live:reassess-sequence",
        (_actor_evidence(scale=(1.1,1.1,1.1)), _material_evidence("dry_surface"), _niagara_evidence("goal_burst")),
        True,
    )
    assessment = assess_reassessment_sequence(plan, failure, result)
    assert assessment.disposition == "replacement_required"
    assert [(step.operation_name, step.disposition) for step in assessment.steps] == [
        ("set_actor_location", "already_applied"),
        ("set_actor_rotation", "replacement_required"),
        ("set_actor_scale", "already_applied"),
        ("apply_material_variant", "replacement_required"),
        ("apply_niagara_variant", "already_applied"),
    ]


def test_replacement_plan_contains_only_mismatched_domains_and_verifiers():
    replacement = build_replacement_plan(_composite_plan(), _mixed_assessment())
    assert [operation.name for operation in replacement.operations] == [
        "set_actor_rotation", "verify_actor_rotation", "apply_material_variant", "verify_material_variant"
    ]
    assert replacement.operations[2].arguments["material_variant"] == {"name": "liquid_surface"}
    assert replacement.operations[3].arguments["material_variant"] == {"name": "liquid_surface"}


def test_reassessment_is_read_only_and_replacement_requires_new_exact_authorization():
    plan = _composite_plan()
    reassessment = build_reassessment_plan(plan, _failure_at(11, "verify_niagara_variant"))
    assert all(operation.kind is UnrealOperationKind.READ for operation in reassessment.operations)
    replacement = build_replacement_plan(plan, _mixed_assessment())
    receipt = issue_replacement_authorization(replacement, "recovery-multi-domain-auth")
    assert receipt.matches(replacement) is True
    assert receipt.matches(plan) is False


def test_sequence_replacement_rejects_stale_reassessment_receipt_before_transport():
    plan = _composite_plan()
    replacement = build_replacement_plan(plan, _mixed_assessment())
    stale = UnrealPlanAuthorization.issue(build_reassessment_plan(plan, _failure_at(11, "verify_niagara_variant")), "stale-reassessment-auth")
    executor = UnrealPlanExecutor(UnrealAdapterProduction(NoTransport()))
    try:
        execute_replacement_authorized(executor, replacement, stale)
    except UnrealPlanExecutionError as exc:
        assert str(exc) == "authorization receipt does not match the exact Unreal task plan"
    else:
        raise AssertionError("stale recovery authorization must not authorize replacement execution")


def test_sequence_replacement_rejects_assessment_operation_name_tampering():
    assessment = UnrealRecoverySequenceAssessment((
        type("Step", (), {"operation_index": 2, "operation_name": "set_actor_scale", "entity_ids": ("FIELD_SURFACE",), "disposition": "replacement_required", "reason": "fresh state differs"})(),
    ))
    try:
        build_replacement_plan(_composite_plan(), assessment)
    except ValueError as exc:
        assert str(exc) == "assessment operation name does not match the source plan"
    else:
        raise AssertionError("recovery assessment must remain bound to its source operation")
