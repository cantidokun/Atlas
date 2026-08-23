"""Fresh-state coordination for failed multi-operation Unreal plans."""

from dataclasses import dataclass
from typing import Mapping, Tuple

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_material_verifier import verify_material_variant
from planning.unreal_niagara_verifier import verify_niagara_variant
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_state_verifier import verify_actor_location, verify_actor_rotation, verify_actor_scale
from planning.unreal_task_planner import UnrealTaskPlan


@dataclass(frozen=True)
class UnrealRecoveryStepAssessment:
    operation_index: int
    operation_name: str
    entity_ids: Tuple[str, ...]
    disposition: str
    reason: str


@dataclass(frozen=True)
class UnrealRecoverySequenceAssessment:
    steps: Tuple[UnrealRecoveryStepAssessment, ...]

    @property
    def disposition(self) -> str:
        if any(step.disposition == "manual_review" for step in self.steps):
            return "manual_review"
        if any(step.disposition == "replacement_required" for step in self.steps):
            return "replacement_required"
        return "already_applied"


@dataclass(frozen=True)
class UnrealRecoverySequenceResult:
    reassessment_result: UnrealPlanExecutionResult
    assessment: UnrealRecoverySequenceAssessment
    replacement_plan: UnrealTaskPlan | None = None
    replacement_result: UnrealPlanExecutionResult | None = None


_WRITE_DEFINITIONS = {
    "set_actor_location": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_location", "location"),
    "set_actor_rotation": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_rotation", "rotation"),
    "set_actor_scale": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_scale", "scale"),
    "apply_material_variant": (UnrealCapability.MATERIAL, "inspect_material_state", "verify_material_variant", "material_variant"),
    "apply_niagara_variant": (UnrealCapability.NIAGARA, "inspect_niagara_state", "verify_niagara_variant", "niagara_variant"),
}

_INSPECTION_CAPABILITIES = {
    "inspect_target_actors": UnrealCapability.INSPECT_ACTOR,
    "inspect_material_state": UnrealCapability.MATERIAL,
    "inspect_niagara_state": UnrealCapability.NIAGARA,
}


def _write_steps(plan: UnrealTaskPlan, failure: UnrealPlanExecutionFailure):
    steps = []
    for index, operation in enumerate(plan.operations):
        if index > failure.operation_index:
            break
        if operation.kind is not UnrealOperationKind.WRITE or operation.name not in _WRITE_DEFINITIONS:
            continue
        capability, inspect_name, verify_name, argument_key = _WRITE_DEFINITIONS[operation.name]
        steps.append((index, operation, capability, inspect_name, verify_name, argument_key))
    if not steps:
        raise ValueError("failed plan contains no supported Unreal write operations before the failure")
    return tuple(steps)


def build_reassessment_plan(plan: UnrealTaskPlan, failure: UnrealPlanExecutionFailure) -> UnrealTaskPlan:
    """Build a read-only plan covering every relevant write through the failure boundary."""
    seen = set()
    operations = []
    for _, operation, _, inspect_name, _, _ in _write_steps(plan, failure):
        key = (inspect_name, tuple(operation.entity_ids))
        if key in seen:
            continue
        seen.add(key)
        inspection_capability = _INSPECTION_CAPABILITIES.get(inspect_name)
        if inspection_capability is None:
            raise ValueError(f"unsupported Unreal recovery inspection operation: {inspect_name}")
        operations.append(
            UnrealOperation(
                capability=inspection_capability,
                kind=UnrealOperationKind.READ,
                name=inspect_name,
                arguments={"entity_ids": tuple(operation.entity_ids)},
                entity_ids=tuple(operation.entity_ids),
            )
        )
    return UnrealTaskPlan(f"{plan.intent_id}:reassess-sequence", tuple(operations))


def _verify(step, evidence):
    _, operation, _, _, _, argument_key = step
    expected = operation.arguments.get(argument_key)
    if not isinstance(expected, Mapping):
        raise ValueError(f"write operation '{operation.name}' has no recoverable target state")
    if operation.name == "set_actor_location":
        verify_actor_location(evidence, expected)
    elif operation.name == "set_actor_rotation":
        verify_actor_rotation(evidence, expected)
    elif operation.name == "set_actor_scale":
        verify_actor_scale(evidence, expected)
    elif operation.name == "apply_material_variant":
        verify_material_variant(evidence, expected)
    elif operation.name == "apply_niagara_variant":
        verify_niagara_variant(evidence, expected)
    else:
        raise ValueError(f"unsupported recovery verifier for '{operation.name}'")


def assess_reassessment_sequence(plan: UnrealTaskPlan, failure: UnrealPlanExecutionFailure, result: UnrealPlanExecutionResult) -> UnrealRecoverySequenceAssessment:
    """Classify every relevant prior write using fresh evidence in plan order."""
    if not isinstance(result, UnrealPlanExecutionResult):
        raise TypeError("result must be a UnrealPlanExecutionResult instance")
    steps = _write_steps(plan, failure)
    if not result.success:
        return UnrealRecoverySequenceAssessment(tuple(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "manual_review", "fresh reassessment did not complete") for index, operation, *_ in steps))

    evidence_by_operation = {}
    for evidence in result.evidence_ledger:
        evidence_by_operation.setdefault((evidence.operation_name, tuple(evidence.entity_ids)), []).append(evidence)

    assessments = []
    for step in steps:
        index, operation, _, inspect_name, _, _ = step
        evidence_list = evidence_by_operation.get((inspect_name, tuple(operation.entity_ids)), [])
        if not evidence_list:
            assessments.append(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "manual_review", "fresh reassessment contains no matching evidence"))
            continue
        try:
            _verify(step, evidence_list[-1])
        except (TypeError, ValueError):
            assessments.append(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "replacement_required", "fresh Unreal state does not match the requested state"))
        else:
            assessments.append(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "already_applied", "fresh Unreal state matches the requested state"))
    return UnrealRecoverySequenceAssessment(tuple(assessments))


def build_replacement_plan(plan: UnrealTaskPlan, assessment: UnrealRecoverySequenceAssessment) -> UnrealTaskPlan:
    """Build a new ordered mutation plan for only the steps requiring replacement."""
    if not isinstance(assessment, UnrealRecoverySequenceAssessment):
        raise TypeError("assessment must be a UnrealRecoverySequenceAssessment instance")
    if any(step.disposition not in {"already_applied", "replacement_required", "manual_review"} for step in assessment.steps):
        raise ValueError("assessment contains an invalid recovery disposition")

    seen_indices = set()
    for step in assessment.steps:
        if step.operation_index in seen_indices:
            raise ValueError("assessment contains duplicate operation indices")
        seen_indices.add(step.operation_index)
        if step.operation_index < 0 or step.operation_index >= len(plan.operations):
            raise ValueError("assessment operation index is outside the source plan")
        source_operation = plan.operations[step.operation_index]
        if source_operation.name != step.operation_name:
            raise ValueError("assessment operation name does not match the source plan")
        if tuple(source_operation.entity_ids) != tuple(step.entity_ids):
            raise ValueError("assessment entity_ids do not match the source plan")

    if any(step.disposition == "manual_review" for step in assessment.steps):
        raise ValueError("replacement plan cannot be built while any recovery step requires manual review")
    replacement_indices = {step.operation_index for step in assessment.steps if step.disposition == "replacement_required"}
    if not replacement_indices:
        raise ValueError("replacement plan requires at least one replacement_required step")

    operations = []
    for index in sorted(replacement_indices):
        operation = plan.operations[index]
        if operation.kind is not UnrealOperationKind.WRITE or operation.name not in _WRITE_DEFINITIONS:
            raise ValueError("recovery replacement assessment must reference supported write operations")
        _, _, verify_name, argument_key = _WRITE_DEFINITIONS[operation.name]
        verify_args = {"entity_ids": tuple(operation.entity_ids)}
        if operation.name in {"set_actor_location", "set_actor_rotation", "set_actor_scale"}:
            verify_args["expected_" + argument_key] = dict(operation.arguments[argument_key])
        else:
            verify_args[argument_key] = dict(operation.arguments[argument_key])
        operations.extend((
            UnrealOperation(operation.capability, UnrealOperationKind.WRITE, operation.name, dict(operation.arguments), tuple(operation.entity_ids)),
            UnrealOperation(operation.capability, UnrealOperationKind.VERIFY, verify_name, verify_args, tuple(operation.entity_ids)),
        ))
    return UnrealTaskPlan(f"{plan.intent_id}:recovery-sequence-replacement", tuple(operations))


def issue_replacement_authorization(replacement_plan: UnrealTaskPlan, authorization_id: str) -> UnrealPlanAuthorization:
    """Issue a new immutable receipt for an exact recovery replacement plan."""
    return UnrealPlanAuthorization.issue(replacement_plan, authorization_id)


def execute_replacement_authorized(executor: UnrealPlanExecutor, replacement_plan: UnrealTaskPlan, authorization: UnrealPlanAuthorization) -> UnrealPlanExecutionResult:
    """Execute only through the exact plan-bound authorization boundary."""
    if not isinstance(executor, UnrealPlanExecutor):
        raise TypeError("executor must be a UnrealPlanExecutor instance")
    if not isinstance(authorization, UnrealPlanAuthorization):
        raise TypeError("authorization must be a UnrealPlanAuthorization instance")
    return executor.execute_authorized(replacement_plan, authorization)


def execute_recovery_sequence(
    executor: UnrealPlanExecutor,
    plan: UnrealTaskPlan,
    failure: UnrealPlanExecutionFailure,
    reassessment_authorization: UnrealPlanAuthorization,
    replacement_authorization: UnrealPlanAuthorization | None = None,
) -> UnrealRecoverySequenceResult:
    """Execute the explicit recovery loop without ever authorizing a mutation implicitly.

    The reassessment receipt is required for the fresh read-only plan. If fresh
    state requires replacement, a separately issued authorization bound to the
    newly constructed replacement plan must be supplied. No replacement receipt
    is created inside this coordinator.
    """
    if not isinstance(executor, UnrealPlanExecutor):
        raise TypeError("executor must be a UnrealPlanExecutor instance")
    if not isinstance(plan, UnrealTaskPlan):
        raise TypeError("plan must be a UnrealTaskPlan instance")
    if not isinstance(failure, UnrealPlanExecutionFailure):
        raise TypeError("failure must be a UnrealPlanExecutionFailure instance")
    if not isinstance(reassessment_authorization, UnrealPlanAuthorization):
        raise TypeError("reassessment_authorization must be a UnrealPlanAuthorization instance")
    if replacement_authorization is not None and not isinstance(replacement_authorization, UnrealPlanAuthorization):
        raise TypeError("replacement_authorization must be a UnrealPlanAuthorization instance or None")

    reassessment_plan = build_reassessment_plan(plan, failure)
    reassessment_result = executor.execute_authorized(reassessment_plan, reassessment_authorization)
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)

    if assessment.disposition == "manual_review":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization must not be supplied for manual review")
        return UnrealRecoverySequenceResult(reassessment_result, assessment)

    if assessment.disposition == "already_applied":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization must not be supplied when recovery is already applied")
        return UnrealRecoverySequenceResult(reassessment_result, assessment)

    replacement_plan = build_replacement_plan(plan, assessment)
    if replacement_authorization is None:
        raise ValueError("replacement_required recovery requires a separate replacement authorization")
    replacement_result = execute_replacement_authorized(executor, replacement_plan, replacement_authorization)
    return UnrealRecoverySequenceResult(reassessment_result, assessment, replacement_plan, replacement_result)
