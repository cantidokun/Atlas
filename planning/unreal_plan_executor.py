"""Deterministic executor for Unreal task plans."""

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Tuple

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation
from planning.unreal_material_verifier import verify_material_variant
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_state_verifier import verify_actor_location, verify_actor_rotation, verify_actor_scale
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_tool_schema import validate_unreal_tool_call


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

    def __post_init__(self) -> None:
        if self.operation_arguments is None:
            object.__setattr__(self, "operation_arguments", {})
        else:
            object.__setattr__(self, "operation_arguments", dict(self.operation_arguments))
        object.__setattr__(self, "completed_operation_arguments", tuple(dict(arguments) for arguments in self.completed_operation_arguments))


class UnrealPlanExecutionError(RuntimeError):
    def __init__(self, message: str, *, failure: Optional[UnrealPlanExecutionFailure] = None):
        super().__init__(message)
        self.failure = failure


@dataclass(frozen=True)
class UnrealPlanExecutionResult:
    intent_id: str
    evidence_ledger: Tuple[UnrealEvidence, ...]
    success: bool


class UnrealPlanExecutor:
    """Execute Unreal plans with mandatory post-write semantic proof."""

    def __init__(self, adapter: UnrealAdapterProduction) -> None:
        if not isinstance(adapter, UnrealAdapterProduction):
            raise TypeError("adapter must be a UnrealAdapterProduction instance")
        self._adapter = adapter

    _DISPATCH = {
        UnrealOperationKind.READ: "inspect",
        UnrealOperationKind.WRITE: "apply_authorized",
        UnrealOperationKind.VERIFY: "verify",
    }

    @staticmethod
    def _validate_execution_shape(plan: UnrealTaskPlan) -> None:
        for index, operation in enumerate(plan.operations):
            if operation.kind is not UnrealOperationKind.WRITE:
                continue
            if index + 1 >= len(plan.operations):
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by verification")
            verification = plan.operations[index + 1]
            if verification.kind is not UnrealOperationKind.VERIFY:
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be immediately followed by verification")
            if tuple(verification.entity_ids) != tuple(operation.entity_ids):
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') and verification must target the same entities")

    def _execute_one(
        self,
        operation: UnrealOperation,
        authorization_id: str,
        expected_location: Optional[dict] = None,
        expected_rotation: Optional[dict] = None,
        expected_scale: Optional[dict] = None,
        expected_material_variant: Optional[dict] = None,
    ) -> UnrealEvidence:
        arguments = dict(operation.arguments)
        arguments["entity_ids"] = tuple(operation.entity_ids)
        arguments["authorization_id"] = authorization_id
        validate_unreal_tool_call(operation.name, arguments)
        method_name = self._DISPATCH.get(operation.kind)
        if method_name is None:
            raise UnrealPlanExecutionError(f"No adapter endpoint for operation kind '{operation.kind.value}'")
        evidence: UnrealEvidence = getattr(self._adapter, method_name)(operation, authorization_id)
        validate_evidence_for_operation(evidence, operation.name, tuple(operation.entity_ids))
        if operation.kind is UnrealOperationKind.VERIFY:
            if expected_location is not None: verify_actor_location(evidence, expected_location)
            if expected_rotation is not None: verify_actor_rotation(evidence, expected_rotation)
            if expected_scale is not None: verify_actor_scale(evidence, expected_scale)
            if expected_material_variant is not None: verify_material_variant(evidence, expected_material_variant)
        return evidence

    @staticmethod
    def _failure_context(operation: UnrealOperation) -> Mapping[str, Any]:
        return dict(operation.arguments)

    def execute_authorized(self, plan: UnrealTaskPlan, authorization: UnrealPlanAuthorization) -> UnrealPlanExecutionResult:
        if not isinstance(authorization, UnrealPlanAuthorization):
            raise TypeError("authorization must be an UnrealPlanAuthorization instance")
        if not authorization.matches(plan):
            raise UnrealPlanExecutionError("authorization receipt does not match the exact Unreal task plan")
        return self.execute(plan, authorization.authorization_id)

    def execute(self, plan: UnrealTaskPlan, authorization_id: str) -> UnrealPlanExecutionResult:
        if not isinstance(plan, UnrealTaskPlan): raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip(): raise UnrealPlanExecutionError("authorization_id must be a non-empty string")
        self._validate_execution_shape(plan)
        ledger: List[UnrealEvidence] = []
        completed_operation_arguments: List[Mapping[str, Any]] = []
        expected_location: Optional[dict] = None
        expected_rotation: Optional[dict] = None
        expected_scale: Optional[dict] = None
        expected_material_variant: Optional[dict] = None

        for index, operation in enumerate(plan.operations):
            if operation.name == "set_actor_location": expected_location, expected_rotation, expected_scale, expected_material_variant = dict(operation.arguments["location"]), None, None, None
            elif operation.name == "set_actor_rotation": expected_location, expected_rotation, expected_scale, expected_material_variant = None, dict(operation.arguments["rotation"]), None, None
            elif operation.name == "set_actor_scale": expected_location, expected_rotation, expected_scale, expected_material_variant = None, None, dict(operation.arguments["scale"]), None
            elif operation.name == "apply_material_variant": expected_location, expected_rotation, expected_scale, expected_material_variant = None, None, None, dict(operation.arguments["material_variant"])
            try:
                evidence = self._execute_one(
                    operation,
                    authorization_id,
                    expected_location if operation.kind is UnrealOperationKind.VERIFY else None,
                    expected_rotation if operation.kind is UnrealOperationKind.VERIFY else None,
                    expected_scale if operation.kind is UnrealOperationKind.VERIFY else None,
                    expected_material_variant if operation.kind is UnrealOperationKind.VERIFY else None,
                )
            except UnrealAdapterError as exc:
                message = f"Operation {index} ('{operation.name}') failed: {exc}"
                failure = UnrealPlanExecutionFailure(plan.intent_id, index, operation.name, tuple(ledger), message, tuple(operation.entity_ids), self._failure_context(operation), tuple(completed_operation_arguments))
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except ValueError as exc:
                message = f"Evidence/tool validation failed for operation {index} ('{operation.name}'): {exc}"
                failure = UnrealPlanExecutionFailure(plan.intent_id, index, operation.name, tuple(ledger), message, tuple(operation.entity_ids), self._failure_context(operation), tuple(completed_operation_arguments))
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except TypeError as exc:
                message = f"Tool argument validation failed for operation {index} ('{operation.name}'): {exc}"
                failure = UnrealPlanExecutionFailure(plan.intent_id, index, operation.name, tuple(ledger), message, tuple(operation.entity_ids), self._failure_context(operation), tuple(completed_operation_arguments))
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except Exception as exc:
                message = f"Unexpected execution failure for operation {index} ('{operation.name}'): {exc}"
                failure = UnrealPlanExecutionFailure(plan.intent_id, index, operation.name, tuple(ledger), message, tuple(operation.entity_ids), self._failure_context(operation), tuple(completed_operation_arguments))
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            ledger.append(evidence)
            completed_operation_arguments.append(self._failure_context(operation))

        return UnrealPlanExecutionResult(plan.intent_id, tuple(ledger), True)
