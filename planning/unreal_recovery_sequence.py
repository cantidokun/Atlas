"""Fresh-state coordination for failed multi-operation Unreal plans."""

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_material_verifier import verify_material_variant
from planning.unreal_niagara_verifier import verify_niagara_variant
from planning.unreal_plan_executor import (
    UnrealPlanExecutionFailure,
    UnrealPlanExecutionResult,
    UnrealRecoveryAssessment,
)
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


_WRITE_DEFINITIONS = {
    "set_actor_location": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_location", "location"),
    "set_actor_rotation": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_rotation", "rotation"),
    "set_actor_scale": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_scale", "scale"),
    "apply_material_variant": (UnrealCapability.MATERIAL, "inspect_material_state", "verify_material_variant", "material_variant"),
    "apply_niagara_variant": (UnrealCapability.NIAGARA, "inspect_niagara_state", "verify_niagara_variant", "niagara_variant"),
}


def _write_steps(plan: UnrealTaskPlan, failure: UnrealPlanExecutionFailure):
    steps = []
    for index, operation in enumerate(plan.operations):
        if index > failure.operation_index:
            break
        if operation.kind is not UnrealOperationKind.WRITE:
            continue
        if operation.name not in _WRITE_DEFINITIONS:
            continue
        capability, inspect_name, verify_name, argument_key = _WRITE_DEFINITIONS[operation.name]
        steps.append((index, operation, capability, inspect_name, verify_name, argument_key))
    if not steps:
        raise ValueError("failed plan contains no supported Unreal write operations before the failure")
    return tuple(steps)


def build_reassessment_plan(plan: UnrealTaskPlan, failure: UnrealPlanExecutionFailure) -> UnrealTaskPlan:
    """Build a read-only plan covering every relevant write through the failure boundary."""
    steps = _write_steps(plan, failure)
    operations = tuple(
        UnrealOperation(
            capability=capability,
            kind=UnrealOperationKind.READ,
            name=inspect_name,
            arguments={"entity_ids": tuple(operation.entity_ids)},
            entity_ids=tuple(operation.entity_ids),
        )
        for _, operation, capability, inspect_name, _, _ in steps
    )
    return UnrealTaskPlan(f"{plan.intent_id}:reassess-sequence", operations)


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


def assess_reassessment_sequence(
    plan: UnrealTaskPlan,
    failure: UnrealPlanExecutionFailure,
    result: UnrealPlanExecutionResult,
) -> UnrealRecoverySequenceAssessment:
    """Classify every relevant prior write using fresh evidence only."""
    if not isinstance(result, UnrealPlanExecutionResult):
        raise TypeError("result must be a UnrealPlanExecutionResult instance")
    if not result.success:
        return UnrealRecoverySequenceAssessment(tuple(
            UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "manual_review", "fresh reassessment did not complete")
            for index, operation, *_ in _write_steps(plan, failure)
        ))

    evidence_by_operation = {}
    for evidence in result.evidence_ledger:
        evidence_by_operation.setdefault(evidence.operation_name, []).append(evidence)

    assessments = []
    for index, operation, _, inspect_name, _, _ in _write_steps(plan, failure):
        evidence_list = evidence_by_operation.get(inspect_name, [])
        matching = [e for e in evidence_list if tuple(e.entity_ids) == tuple(operation.entity_ids)]
        if not matching:
            assessments.append(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "manual_review", "fresh reassessment contains no matching evidence"))
            continue
        try:
            _verify((index, operation, *_WRITE_DEFINITIONS[operation.name]), matching[-1])
        except (TypeError, ValueError):
            assessments.append(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "replacement_required", "fresh Unreal state does not match the requested state"))
        else:
            assessments.append(UnrealRecoveryStepAssessment(index, operation.name, tuple(operation.entity_ids), "already_applied", "fresh Unreal state matches the requested state"))
    return UnrealRecoverySequenceAssessment(tuple(assessments))


def build_replacement_plan(
    plan: UnrealTaskPlan,
    assessment: UnrealRecoverySequenceAssessment,
) -> UnrealTaskPlan:
    """Build a new ordered mutation plan for only the steps requiring replacement."""
    if not isinstance(assessment, UnrealRecoverySequenceAssessment):
        raise TypeError("assessment must be a UnrealRecoverySequenceAssessment instance")
    replacement_indices = {step.operation_index for step in assessment.steps if step.disposition == "replacement_required"}
    if not replacement_indices:
        raise ValueError("replacement plan requires at least one replacement_required step")
    if any(step.disposition not in {"already_applied", "replacement_required", "manual_review"} for step in assessment.steps):
        raise ValueError("assessment contains an invalid recovery disposition")
    if any(step.disposition == "manual_review" for step in assessment.steps):
        raise ValueError("replacement plan cannot be built while any recovery step requires manual review")

    operations = []
    for index in sorted(replacement_indices):
        operation = plan.operations[index]
        if operation.kind is not UnrealOperationKind.WRITE:
            raise ValueError("recovery replacement assessment must reference write operations")
        _, _, _, verify_name, argument_key = _WRITE_DEFINITIONS[operation.name]
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
