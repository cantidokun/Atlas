"""Production-aware recovery for heterogeneous Unreal transactions.

Recovery never mutates the original production plan and never reuses its
authorization. A failed production transaction is first reassessed through a
fresh, read-only plan. Only mismatched writes are then placed into a new
replacement plan, which must receive an independent authorization receipt.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_material_verifier import verify_material_variant
from planning.unreal_niagara_verifier import verify_niagara_variant
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import (
    UnrealPlanExecutionFailure,
    UnrealPlanExecutionResult,
    UnrealPlanExecutor,
)
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_render_contract import verify_render_config
from planning.unreal_sequencer_verifier import verify_sequencer_playback_range
from planning.unreal_state_verifier import verify_actor_location, verify_actor_rotation, verify_actor_scale
from planning.unreal_task_planner import UnrealTaskPlan


@dataclass(frozen=True)
class UnrealProductionRecoveryStep:
    operation_index: int
    operation_name: str
    phase: str
    entity_ids: Tuple[str, ...]
    disposition: str
    reason: str


@dataclass(frozen=True)
class UnrealProductionRecoveryAssessment:
    steps: Tuple[UnrealProductionRecoveryStep, ...]

    @property
    def disposition(self) -> str:
        if any(step.disposition == "manual_review" for step in self.steps):
            return "manual_review"
        if any(step.disposition == "replacement_required" for step in self.steps):
            return "replacement_required"
        return "already_applied"


@dataclass(frozen=True)
class UnrealProductionRecoveryResult:
    reassessment_plan: UnrealTaskPlan
    reassessment_result: UnrealPlanExecutionResult
    assessment: UnrealProductionRecoveryAssessment
    replacement_plan: Optional[UnrealTaskPlan] = None
    replacement_result: Optional[UnrealPlanExecutionResult] = None


_WRITE_DEFINITIONS = {
    "set_actor_location": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_location"),
    "set_actor_rotation": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_rotation"),
    "set_actor_scale": (UnrealCapability.MODIFY_ACTOR, "inspect_target_actors", "verify_actor_scale"),
    "apply_material_variant": (UnrealCapability.MATERIAL, "inspect_material_state", "verify_material_variant"),
    "apply_niagara_variant": (UnrealCapability.NIAGARA, "inspect_niagara_state", "verify_niagara_variant"),
    "set_sequencer_playback_range": (UnrealCapability.SEQUENCER, "inspect_sequencer_state", "verify_sequencer_playback_range"),
    "compile_blueprint": (UnrealCapability.BLUEPRINT, "inspect_blueprint_state", "verify_blueprint_state"),
    "configure_render": (UnrealCapability.RENDER, "inspect_render_state", "verify_render_state"),
}

_INSPECTION_CAPABILITIES = {
    "inspect_target_actors": UnrealCapability.INSPECT_ACTOR,
    "inspect_material_state": UnrealCapability.MATERIAL,
    "inspect_niagara_state": UnrealCapability.NIAGARA,
    "inspect_sequencer_state": UnrealCapability.SEQUENCER,
    "inspect_blueprint_state": UnrealCapability.BLUEPRINT,
    "inspect_render_state": UnrealCapability.RENDER,
}


def _phase_for_index(production: UnrealProductionPlan, index: int) -> str:
    for phase_name, start, end in production.phases:
        if start <= index < end:
            return phase_name
    raise ValueError("operation index is outside the production phase boundaries")


def _validate_failure_binding(production: UnrealProductionPlan, failure: UnrealPlanExecutionFailure) -> None:
    if failure.intent_id != production.plan.intent_id:
        raise ValueError("recovery failure intent_id does not match the production plan")
    if failure.operation_index < 0 or failure.operation_index >= len(production.plan.operations):
        raise ValueError("recovery failure operation_index is outside the production plan")
    operation = production.plan.operations[failure.operation_index]
    if operation.name != failure.operation_name:
        raise ValueError("recovery failure operation_name does not match the production plan")
    if tuple(operation.entity_ids) != tuple(failure.operation_entity_ids):
        raise ValueError("recovery failure entity_ids do not match the production plan")


def failed_phase(production: UnrealProductionPlan, failure: UnrealPlanExecutionFailure) -> str:
    """Return the deterministic production phase containing the failed operation."""
    _validate_failure_binding(production, failure)
    return _phase_for_index(production, failure.operation_index)


def _supported_writes(production: UnrealProductionPlan, failure: UnrealPlanExecutionFailure):
    _validate_failure_binding(production, failure)
    steps = []
    for index, operation in enumerate(production.plan.operations):
        if index > failure.operation_index:
            break
        if operation.kind is UnrealOperationKind.WRITE and operation.name in _WRITE_DEFINITIONS:
            capability, inspect_name, verify_name = _WRITE_DEFINITIONS[operation.name]
            steps.append((index, operation, capability, inspect_name, verify_name))
    if not steps:
        raise ValueError("failed production contains no supported writes before the failure")
    return tuple(steps)


def build_production_reassessment_plan(
    production: UnrealProductionPlan,
    failure: UnrealPlanExecutionFailure,
) -> UnrealTaskPlan:
    """Build one fresh read-only plan covering all writes through the failure."""
    seen = set()
    operations = []
    for _, operation, _, inspect_name, _ in _supported_writes(production, failure):
        key = (inspect_name, tuple(operation.entity_ids), operation.arguments.get("asset_path"))
        if key in seen:
            continue
        seen.add(key)
        capability = _INSPECTION_CAPABILITIES[inspect_name]
        arguments = {"entity_ids": tuple(operation.entity_ids)}
        if inspect_name == "inspect_blueprint_state":
            arguments["asset_path"] = operation.arguments["asset_path"]
        operations.append(
            UnrealOperation(
                capability=capability,
                kind=UnrealOperationKind.READ,
                name=inspect_name,
                arguments=arguments,
                entity_ids=tuple(operation.entity_ids),
            )
        )
    return UnrealTaskPlan(f"{production.plan.intent_id}:production-reassess", tuple(operations))


def _expected(operation) -> Mapping[str, Any]:
    args = operation.arguments
    if operation.name == "set_actor_location":
        return {"location": dict(args["location"])}
    if operation.name == "set_actor_rotation":
        return {"rotation": dict(args["rotation"])}
    if operation.name == "set_actor_scale":
        return {"scale": dict(args["scale"])}
    if operation.name == "apply_material_variant":
        return {"material_variant": dict(args["material_variant"])}
    if operation.name == "apply_niagara_variant":
        return {"niagara_variant": dict(args["niagara_variant"])}
    if operation.name == "set_sequencer_playback_range":
        return {"start_frame": int(args["start_frame"]), "end_frame": int(args["end_frame"])}
    if operation.name == "compile_blueprint":
        return {"asset_path": args["asset_path"], "compile_status": "success"}
    if operation.name == "configure_render":
        return {key: args[key] for key in ("width", "height", "start_frame", "end_frame", "output_directory", "output_format")}
    raise ValueError(f"unsupported production recovery operation: {operation.name}")


def _state(evidence: UnrealEvidence, entity_id: str, key: str) -> Mapping[str, Any]:
    observed = evidence.observed_state.get(entity_id)
    if not isinstance(observed, Mapping):
        raise ValueError("fresh evidence does not contain the expected entity state")
    value = observed.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"fresh evidence does not contain the expected {key} state")
    return value


def _verify(operation, evidence: UnrealEvidence) -> None:
    expected = _expected(operation)
    entity_id = operation.entity_ids[0]
    if operation.name == "set_actor_location":
        verify_actor_location(evidence, expected["location"])
    elif operation.name == "set_actor_rotation":
        verify_actor_rotation(evidence, expected["rotation"])
    elif operation.name == "set_actor_scale":
        verify_actor_scale(evidence, expected["scale"])
    elif operation.name == "apply_material_variant":
        verify_material_variant(evidence, expected["material_variant"])
    elif operation.name == "apply_niagara_variant":
        verify_niagara_variant(evidence, expected["niagara_variant"])
    elif operation.name == "set_sequencer_playback_range":
        verify_sequencer_playback_range(evidence, expected["start_frame"], expected["end_frame"])
    elif operation.name == "compile_blueprint":
        state = _state(evidence, entity_id, "blueprint")
        if state.get("asset_path") != expected["asset_path"] or state.get("compile_status") != expected["compile_status"]:
            raise ValueError("fresh Unreal Blueprint state does not match the requested compiled state")
    elif operation.name == "configure_render":
        verify_render_config(evidence, expected)
    else:
        raise ValueError(f"unsupported production recovery verifier: {operation.name}")


def assess_production_reassessment(
    production: UnrealProductionPlan,
    failure: UnrealPlanExecutionFailure,
    result: UnrealPlanExecutionResult,
) -> UnrealProductionRecoveryAssessment:
    """Classify every relevant prior write from fresh evidence only."""
    if not isinstance(result, UnrealPlanExecutionResult):
        raise TypeError("result must be a UnrealPlanExecutionResult instance")
    steps = _supported_writes(production, failure)
    if not result.success:
        return UnrealProductionRecoveryAssessment(tuple(
            UnrealProductionRecoveryStep(i, op.name, _phase_for_index(production, i), tuple(op.entity_ids), "manual_review", "fresh reassessment did not complete")
            for i, op, *_ in steps
        ))

    evidence_by_operation = {}
    for evidence in result.evidence_ledger:
        evidence_by_operation[(evidence.operation_name, tuple(evidence.entity_ids))] = evidence

    assessments = []
    for index, operation, _, inspect_name, _ in steps:
        evidence = evidence_by_operation.get((inspect_name, tuple(operation.entity_ids)))
        phase = _phase_for_index(production, index)
        if evidence is None:
            assessments.append(UnrealProductionRecoveryStep(index, operation.name, phase, tuple(operation.entity_ids), "manual_review", "fresh reassessment contains no matching evidence"))
            continue
        try:
            _verify(operation, evidence)
        except (TypeError, ValueError, KeyError, IndexError):
            disposition = "replacement_required"
            reason = "fresh Unreal state does not match the requested state"
        else:
            disposition = "already_applied"
            reason = "fresh Unreal state matches the requested state"
        assessments.append(UnrealProductionRecoveryStep(index, operation.name, phase, tuple(operation.entity_ids), disposition, reason))
    return UnrealProductionRecoveryAssessment(tuple(assessments))


def build_production_replacement_plan(
    production: UnrealProductionPlan,
    assessment: UnrealProductionRecoveryAssessment,
) -> UnrealTaskPlan:
    """Build a new mutation/verification plan containing only mismatched writes."""
    if any(step.disposition == "manual_review" for step in assessment.steps):
        raise ValueError("replacement plan cannot be built while any recovery step requires manual review")
    replacements = {step.operation_index for step in assessment.steps if step.disposition == "replacement_required"}
    if not replacements:
        raise ValueError("replacement plan requires at least one replacement_required step")

    operations = []
    for index in sorted(replacements):
        step = next(step for step in assessment.steps if step.operation_index == index)
        source = production.plan.operations[index]
        if source.kind is not UnrealOperationKind.WRITE or source.name not in _WRITE_DEFINITIONS:
            raise ValueError("assessment references an unsupported production write")
        _, _, verify_name = _WRITE_DEFINITIONS[source.name]
        write_arguments = {"entity_ids": tuple(source.entity_ids), **{k: v for k, v in source.arguments.items() if k != "entity_ids"}}
        verify_arguments = {"entity_ids": tuple(source.entity_ids)}
        if source.name == "set_actor_location":
            verify_arguments["expected_location"] = dict(source.arguments["location"])
        elif source.name == "set_actor_rotation":
            verify_arguments["expected_rotation"] = dict(source.arguments["rotation"])
        elif source.name == "set_actor_scale":
            verify_arguments["expected_scale"] = dict(source.arguments["scale"])
        elif source.name == "apply_material_variant":
            verify_arguments["material_variant"] = dict(source.arguments["material_variant"])
        elif source.name == "apply_niagara_variant":
            verify_arguments["niagara_variant"] = dict(source.arguments["niagara_variant"])
        elif source.name == "set_sequencer_playback_range":
            verify_arguments.update(expected_start_frame=int(source.arguments["start_frame"]), expected_end_frame=int(source.arguments["end_frame"]))
        elif source.name == "compile_blueprint":
            verify_arguments.update(asset_path=source.arguments["asset_path"], expected_compile_status="success")
        elif source.name == "configure_render":
            verify_arguments.update({key: source.arguments[key] for key in ("width", "height", "start_frame", "end_frame", "output_directory", "output_format")})
        operations.extend((
            UnrealOperation(source.capability, UnrealOperationKind.WRITE, source.name, write_arguments, tuple(source.entity_ids)),
            UnrealOperation(source.capability, UnrealOperationKind.VERIFY, verify_name, verify_arguments, tuple(source.entity_ids)),
        ))
    return UnrealTaskPlan(f"{production.plan.intent_id}:production-recovery-replacement", tuple(operations))


def issue_production_replacement_authorization(plan: UnrealTaskPlan, authorization_id: str) -> UnrealPlanAuthorization:
    return UnrealPlanAuthorization.issue(plan, authorization_id)


def execute_production_recovery(
    executor: UnrealPlanExecutor,
    production: UnrealProductionPlan,
    failure: UnrealPlanExecutionFailure,
    reassessment_authorization: UnrealPlanAuthorization,
    replacement_authorization: Optional[UnrealPlanAuthorization] = None,
) -> UnrealProductionRecoveryResult:
    """Run reassessment and, only when required, an independently authorized replacement."""
    if not isinstance(executor, UnrealPlanExecutor):
        raise TypeError("executor must be a UnrealPlanExecutor instance")
    if not isinstance(production, UnrealProductionPlan):
        raise TypeError("production must be an UnrealProductionPlan instance")
    if not isinstance(failure, UnrealPlanExecutionFailure):
        raise TypeError("failure must be an UnrealPlanExecutionFailure instance")
    if not isinstance(reassessment_authorization, UnrealPlanAuthorization):
        raise TypeError("reassessment_authorization must be a UnrealPlanAuthorization instance")

    reassessment_plan = build_production_reassessment_plan(production, failure)
    if not reassessment_authorization.matches(reassessment_plan):
        raise ValueError("reassessment authorization does not match the exact production reassessment plan")
    reassessment_result = executor.execute_authorized(reassessment_plan, reassessment_authorization)
    assessment = assess_production_reassessment(production, failure, reassessment_result)

    if assessment.disposition != "replacement_required":
        if replacement_authorization is not None:
            raise ValueError("replacement authorization is only valid when replacement is required")
        return UnrealProductionRecoveryResult(reassessment_plan, reassessment_result, assessment)

    replacement_plan = build_production_replacement_plan(production, assessment)
    if replacement_authorization is None:
        raise ValueError("replacement_required recovery requires a separate replacement authorization")
    if not replacement_authorization.matches(replacement_plan):
        raise ValueError("replacement authorization does not match the exact production replacement plan")
    replacement_result = executor.execute_authorized(replacement_plan, replacement_authorization)
    return UnrealProductionRecoveryResult(reassessment_plan, reassessment_result, assessment, replacement_plan, replacement_result)
