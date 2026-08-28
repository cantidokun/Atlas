"""Deterministic executor for Unreal task plans."""

from dataclasses import dataclass, replace
from typing import Any, Mapping, Tuple

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation
from planning.unreal_material_verifier import verify_material_variant
from planning.unreal_niagara_verifier import verify_niagara_variant
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_state_verifier import verify_actor_location, verify_actor_rotation, verify_actor_scale
from planning.unreal_sequencer_verifier import verify_sequencer_playback_range
from planning.unreal_render_contract import verify_render_config
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_tool_schema import validate_unreal_tool_call


@dataclass(frozen=True)
class UnrealRecoveryAssessment:
    """Fresh-state recovery disposition derived from a reassessment result."""

    disposition: str
    operation_name: str
    entity_ids: Tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class UnrealPlanExecutionFailure:
    intent_id: str
    operation_index: int
    operation_name: str
    completed_evidence: Tuple[UnrealEvidence, ...]
    error: str
    operation_entity_ids: Tuple[str, ...] = ()
    operation_arguments: Mapping[str, Any] = None
    completed_operation_arguments: Tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "operation_arguments", {} if self.operation_arguments is None else dict(self.operation_arguments))
        object.__setattr__(self, "completed_operation_arguments", tuple(dict(a) for a in self.completed_operation_arguments))
        object.__setattr__(self, "operation_entity_ids", tuple(self.operation_entity_ids))

    def reassessment_plan(self) -> UnrealTaskPlan:
        """Create a read-only, fresh-state plan for explicit recovery coordination."""
        if not self.operation_entity_ids:
            raise ValueError("failure must contain operation_entity_ids for recovery reassessment")
        entity_ids = tuple(self.operation_entity_ids)
        operations = (
            UnrealOperation(
                capability=UnrealCapability.INSPECT_ACTOR,
                kind=UnrealOperationKind.READ,
                name="inspect_target_actors",
                arguments={"entity_ids": entity_ids},
                entity_ids=entity_ids,
            ),
            UnrealOperation(
                capability=UnrealCapability.INSPECT_ACTOR,
                kind=UnrealOperationKind.VERIFY,
                name="verify_target_actor_mapping",
                arguments={"entity_ids": entity_ids},
                entity_ids=entity_ids,
            ),
        )
        return UnrealTaskPlan(f"{self.intent_id}:reassess", operations)

    def assess_reassessment(self, result: "UnrealPlanExecutionResult") -> UnrealRecoveryAssessment:
        """Classify fresh state without authorizing or replaying a mutation."""
        if not isinstance(result, UnrealPlanExecutionResult):
            raise TypeError("result must be a UnrealPlanExecutionResult instance")
        if not result.success or not result.evidence_ledger:
            return UnrealRecoveryAssessment("manual_review", self.operation_name, tuple(self.operation_entity_ids), "fresh reassessment did not produce usable evidence")
        evidence = result.evidence_ledger[-1]
        expected = self._recovery_expectation()
        if not expected:
            return UnrealRecoveryAssessment("manual_review", self.operation_name, tuple(self.operation_entity_ids), "failed operation has no supported recovery-state comparator")
        try:
            if "location" in expected: verify_actor_location(evidence, expected["location"])
            elif "rotation" in expected: verify_actor_rotation(evidence, expected["rotation"])
            elif "scale" in expected: verify_actor_scale(evidence, expected["scale"])
            elif "material_variant" in expected: verify_material_variant(evidence, expected["material_variant"])
            elif "niagara_variant" in expected: verify_niagara_variant(evidence, expected["niagara_variant"])
            elif "start_frame" in expected and "end_frame" in expected: verify_sequencer_playback_range(evidence, expected["start_frame"], expected["end_frame"])
        except (TypeError, ValueError):
            return UnrealRecoveryAssessment("replacement_required", self.operation_name, tuple(self.operation_entity_ids), "fresh Unreal state does not match the failed operation's requested state")
        return UnrealRecoveryAssessment("already_applied", self.operation_name, tuple(self.operation_entity_ids), "fresh Unreal state already matches the failed operation's requested state")

    def replacement_plan(self, assessment: UnrealRecoveryAssessment) -> UnrealTaskPlan:
        """Build a new mutation plan from a replacement-required recovery decision.

        This method never reuses the failed authorization. The caller must issue
        a fresh UnrealPlanAuthorization receipt for the returned plan before
        executing it through execute_authorized().
        """
        if not isinstance(assessment, UnrealRecoveryAssessment):
            raise TypeError("assessment must be an UnrealRecoveryAssessment instance")
        if assessment.disposition != "replacement_required":
            raise ValueError("replacement_plan requires a replacement_required assessment")
        if tuple(assessment.entity_ids) != tuple(self.operation_entity_ids):
            raise ValueError("assessment entity_ids must match failed operation entity_ids")

        ids = tuple(assessment.entity_ids)
        args = self.operation_arguments
        if self.operation_name in {"set_actor_location", "verify_actor_location"}:
            location = args.get("location", args.get("expected_location"))
            if not isinstance(location, Mapping):
                raise ValueError("failed location operation does not contain a recoverable location")
            normalized = dict(location)
            ops = (
                UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", {"entity_ids": ids, "location": normalized}, ids),
                UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_location", {"entity_ids": ids, "expected_location": normalized}, ids),
            )
        elif self.operation_name in {"set_actor_rotation", "verify_actor_rotation"}:
            rotation = args.get("rotation", args.get("expected_rotation"))
            if not isinstance(rotation, Mapping): raise ValueError("failed rotation operation does not contain a recoverable rotation")
            normalized = dict(rotation)
            ops = (
                UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_rotation", {"entity_ids": ids, "rotation": normalized}, ids),
                UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_rotation", {"entity_ids": ids, "expected_rotation": normalized}, ids),
            )
        elif self.operation_name in {"set_actor_scale", "verify_actor_scale"}:
            scale = args.get("scale", args.get("expected_scale"))
            if not isinstance(scale, Mapping): raise ValueError("failed scale operation does not contain a recoverable scale")
            normalized = dict(scale)
            ops = (
                UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_scale", {"entity_ids": ids, "scale": normalized}, ids),
                UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_scale", {"entity_ids": ids, "expected_scale": normalized}, ids),
            )
        elif self.operation_name in {"apply_material_variant", "verify_material_variant"}:
            variant = args.get("material_variant", args.get("expected_material_variant"))
            if not isinstance(variant, Mapping): raise ValueError("failed material operation does not contain a recoverable material variant")
            normalized = dict(variant)
            ops = (
                UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.WRITE, "apply_material_variant", {"entity_ids": ids, "material_variant": normalized}, ids),
                UnrealOperation(UnrealCapability.MATERIAL, UnrealOperationKind.VERIFY, "verify_material_variant", {"entity_ids": ids, "material_variant": normalized}, ids),
            )
        elif self.operation_name in {"apply_niagara_variant", "verify_niagara_variant"}:
            variant = args.get("niagara_variant", args.get("expected_niagara_variant"))
            if not isinstance(variant, Mapping): raise ValueError("failed Niagara operation does not contain a recoverable Niagara variant")
            normalized = dict(variant)
            ops = (
                UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.WRITE, "apply_niagara_variant", {"entity_ids": ids, "niagara_variant": normalized}, ids),
                UnrealOperation(UnrealCapability.NIAGARA, UnrealOperationKind.VERIFY, "verify_niagara_variant", {"entity_ids": ids, "niagara_variant": normalized}, ids),
            )
        elif self.operation_name in {"set_sequencer_playback_range", "verify_sequencer_playback_range"}:
            start_frame = args.get("start_frame", args.get("expected_start_frame"))
            end_frame = args.get("end_frame", args.get("expected_end_frame"))
            if start_frame is None or end_frame is None:
                raise ValueError("failed sequencer operation does not contain recoverable start_frame and end_frame")
            ops = (
                UnrealOperation(UnrealCapability.SEQUENCER, UnrealOperationKind.WRITE, "set_sequencer_playback_range", {"entity_ids": ids, "start_frame": start_frame, "end_frame": end_frame}, ids),
                UnrealOperation(UnrealCapability.SEQUENCER, UnrealOperationKind.VERIFY, "verify_sequencer_playback_range", {"entity_ids": ids, "expected_start_frame": start_frame, "expected_end_frame": end_frame}, ids),
            )
        else:
            raise ValueError(f"unsupported recovery replacement operation: {self.operation_name}")
        return UnrealTaskPlan(f"{self.intent_id}:recovery-replacement", ops)

    def _recovery_expectation(self):
        arguments = self.operation_arguments
        if self.operation_name == "set_actor_location": return {"location": arguments.get("location")}
        if self.operation_name == "verify_actor_location": return {"location": arguments.get("expected_location")}
        if self.operation_name == "set_actor_rotation": return {"rotation": arguments.get("rotation")}
        if self.operation_name == "verify_actor_rotation": return {"rotation": arguments.get("expected_rotation")}
        if self.operation_name == "set_actor_scale": return {"scale": arguments.get("scale")}
        if self.operation_name == "verify_actor_scale": return {"scale": arguments.get("expected_scale")}
        if self.operation_name == "apply_material_variant": return {"material_variant": arguments.get("material_variant")}
        if self.operation_name == "verify_material_variant": return {"material_variant": arguments.get("expected_material_variant")}
        if self.operation_name == "apply_niagara_variant": return {"niagara_variant": arguments.get("niagara_variant")}
        if self.operation_name == "verify_niagara_variant": return {"niagara_variant": arguments.get("expected_niagara_variant")}
        if self.operation_name == "set_sequencer_playback_range": return {"start_frame": arguments.get("start_frame"), "end_frame": arguments.get("end_frame")}
        if self.operation_name == "verify_sequencer_playback_range": return {"start_frame": arguments.get("expected_start_frame"), "end_frame": arguments.get("expected_end_frame")}
        return {}


class UnrealPlanExecutionError(RuntimeError):
    def __init__(self, message, *, failure=None):
        super().__init__(message)
        self.failure = failure


@dataclass(frozen=True)
class UnrealPlanExecutionResult:
    intent_id: str
    evidence_ledger: Tuple[UnrealEvidence, ...]
    success: bool


class UnrealPlanExecutor:
    def __init__(self, adapter: UnrealAdapterProduction):
        if not isinstance(adapter, UnrealAdapterProduction): raise TypeError("adapter must be a UnrealAdapterProduction instance")
        self._adapter = adapter
        self._capabilities = UnrealCapabilityRegistry()
    _DISPATCH = {UnrealOperationKind.READ: "inspect", UnrealOperationKind.WRITE: "apply_authorized", UnrealOperationKind.VERIFY: "verify"}
    @staticmethod
    def _expected_verifier(write_operation):
        return {"set_actor_location":"verify_actor_location","set_actor_rotation":"verify_actor_rotation","set_actor_scale":"verify_actor_scale","apply_material_variant":"verify_material_variant","apply_niagara_variant":"verify_niagara_variant","set_sequencer_playback_range":"verify_sequencer_playback_range","configure_render":"verify_render_state","compile_blueprint":"verify_blueprint_state"}.get(write_operation.name)
    @classmethod
    def _validate_execution_shape(cls, plan):
        for index, operation in enumerate(plan.operations):
            if operation.kind is not UnrealOperationKind.WRITE:
                continue
            if index + 1 >= len(plan.operations):
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by verification")
            verification = plan.operations[index + 1]

            # Blueprint metadata is intentionally staged through compilation:
            # inspect -> set metadata -> compile -> verify. The metadata write
            # is not independently verifiable until the compiled Blueprint has
            # been saved by the compile operation.
            if operation.name == "set_blueprint_metadata":
                if verification.name != "compile_blueprint" or verification.kind is not UnrealOperationKind.WRITE:
                    raise UnrealPlanExecutionError(
                        f"Write operation {index} ('{operation.name}') must be followed by 'compile_blueprint'"
                    )
                if tuple(verification.entity_ids) != tuple(operation.entity_ids):
                    raise UnrealPlanExecutionError(
                        f"Write operation {index} ('{operation.name}') and compilation must target the same entities"
                    )
                continue

            if verification.kind is not UnrealOperationKind.VERIFY:
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be immediately followed by verification")
            if tuple(verification.entity_ids) != tuple(operation.entity_ids):
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') and verification must target the same entities")
            expected = cls._expected_verifier(operation)
            if expected is not None and verification.name != expected:
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by '{expected}', not '{verification.name}'")
    @staticmethod
    def _format_preflight_error(exc):
        message=str(exc)
        return "location must contain exactly x, y, and z" if message=="location must contain exactly x, y, z" else message
    def _preflight_plan(self, plan):
        for index, operation in enumerate(plan.operations):
            try: self._capabilities.validate_operation(operation)
            except (KeyError,TypeError,ValueError) as exc: raise UnrealPlanExecutionError(f"Operation {index} ('{operation.name}') failed preflight: {self._format_preflight_error(exc)}") from exc
    @staticmethod
    def _verification_expectation(write_operation):
        a=write_operation.arguments
        if write_operation.name=="set_actor_location": return {"location":dict(a["location"])}
        if write_operation.name=="set_actor_rotation": return {"rotation":dict(a["rotation"])}
        if write_operation.name=="set_actor_scale": return {"scale":dict(a["scale"])}
        if write_operation.name=="apply_material_variant": return {"material_variant":dict(a["material_variant"])}
        if write_operation.name=="apply_niagara_variant": return {"niagara_variant":dict(a["niagara_variant"])}
        if write_operation.name=="set_sequencer_playback_range": return {"start_frame":a["start_frame"],"end_frame":a["end_frame"]}
        if write_operation.name=="configure_render": return {key:a[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")}
        return {}
    @staticmethod
    def _is_semantically_verified(operation,evidence): return operation.name in {"verify_actor_location","verify_actor_rotation","verify_actor_scale","verify_material_variant","verify_niagara_variant","verify_sequencer_playback_range"}
    def _execute_one(self,operation,authorization_id,*,expected_location=None,expected_rotation=None,expected_scale=None,expected_material_variant=None,expected_niagara_variant=None,expected_start_frame=None,expected_end_frame=None):
        arguments=dict(operation.arguments); arguments["entity_ids"]=tuple(operation.entity_ids); arguments["authorization_id"]=authorization_id; validate_unreal_tool_call(operation.name,arguments)
        method_name=self._DISPATCH[operation.kind]; evidence=getattr(self._adapter,method_name)(operation,authorization_id); validate_evidence_for_operation(evidence,operation.name,tuple(operation.entity_ids))
        if operation.kind is UnrealOperationKind.VERIFY:
            if expected_location is not None: evidence=verify_actor_location(evidence,expected_location)
            if expected_rotation is not None: evidence=verify_actor_rotation(evidence,expected_rotation)
            if expected_scale is not None: evidence=verify_actor_scale(evidence,expected_scale)
            if expected_material_variant is not None: evidence=verify_material_variant(evidence,expected_material_variant)
            if expected_niagara_variant is not None: evidence=verify_niagara_variant(evidence,expected_niagara_variant)
            if expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)
            if operation.name == "verify_render_state": evidence=verify_render_config(evidence, {key: operation.arguments[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")})
            if self._is_semantically_verified(operation,evidence): evidence=replace(evidence,verified=True)
        return evidence
    @staticmethod
    def _failure_context(operation): return dict(operation.arguments)
    def execute_authorized(self,plan,authorization):
        if not isinstance(authorization,UnrealPlanAuthorization): raise TypeError("authorization must be a UnrealPlanAuthorization instance")
        if not authorization.matches(plan): raise UnrealPlanExecutionError("authorization receipt does not match the exact Unreal task plan")
        return self.execute(plan,authorization.authorization_id)
    def execute(self,plan,authorization_id):
        if not isinstance(plan,UnrealTaskPlan): raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id,str) or not authorization_id.strip(): raise UnrealPlanExecutionError("authorization_id must be a non-empty string")
        self._validate_execution_shape(plan); self._preflight_plan(plan); ledger=[]; completed=[]
        for index,operation in enumerate(plan.operations):
            expected={}
            if operation.kind is UnrealOperationKind.VERIFY:
                previous=plan.operations[index-1] if index else None
                if previous is None or previous.kind not in (UnrealOperationKind.WRITE,UnrealOperationKind.READ): raise UnrealPlanExecutionError(f"Verify operation {index} ('{operation.name}') must follow a read or write")
                if previous.kind is UnrealOperationKind.WRITE: expected=self._verification_expectation(previous)
            try: evidence=self._execute_one(operation,authorization_id,expected_location=expected.get("location"),expected_rotation=expected.get("rotation"),expected_scale=expected.get("scale"),expected_material_variant=expected.get("material_variant"),expected_niagara_variant=expected.get("niagara_variant"),expected_start_frame=expected.get("start_frame"),expected_end_frame=expected.get("end_frame"))
            except (UnrealAdapterError,ValueError,TypeError) as exc:
                message=f"Operation {index} ('{operation.name}') failed: {exc}"; failure=UnrealPlanExecutionFailure(plan.intent_id,index,operation.name,tuple(ledger),message,tuple(operation.entity_ids),self._failure_context(operation),tuple(completed)); raise UnrealPlanExecutionError(message,failure=failure) from exc
            except Exception as exc:
                message=f"Unexpected execution failure for operation {index} ('{operation.name}'):\n{exc}"; failure=UnrealPlanExecutionFailure(plan.intent_id,index,operation.name,tuple(ledger),message,tuple(operation.entity_ids),self._failure_context(operation),tuple(completed)); raise UnrealPlanExecutionError(message,failure=failure) from exc
            ledger.append(evidence); completed.append(self._failure_context(operation))
        return UnrealPlanExecutionResult(plan.intent_id,tuple(ledger),True)
