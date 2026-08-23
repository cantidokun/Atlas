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
            return UnrealRecoveryAssessment(
                "manual_review", self.operation_name, tuple(self.operation_entity_ids),
                "fresh reassessment did not produce usable evidence",
            )

        evidence = result.evidence_ledger[-1]
        expected = self._recovery_expectation()
        if not expected:
            return UnrealRecoveryAssessment(
                "manual_review", self.operation_name, tuple(self.operation_entity_ids),
                "failed operation has no supported recovery-state comparator",
            )

        probe = evidence
        try:
            if "location" in expected:
                probe = verify_actor_location(probe, expected["location"])
            elif "rotation" in expected:
                probe = verify_actor_rotation(probe, expected["rotation"])
            elif "scale" in expected:
                probe = verify_actor_scale(probe, expected["scale"])
            elif "material_variant" in expected:
                probe = verify_material_variant(probe, expected["material_variant"])
            elif "niagara_variant" in expected:
                probe = verify_niagara_variant(probe, expected["niagara_variant"])
        except (TypeError, ValueError):
            return UnrealRecoveryAssessment(
                "replacement_required", self.operation_name, tuple(self.operation_entity_ids),
                "fresh Unreal state does not match the failed operation's requested state",
            )

        return UnrealRecoveryAssessment(
            "already_applied", self.operation_name, tuple(self.operation_entity_ids),
            "fresh Unreal state already matches the failed operation's requested state",
        )

    def _recovery_expectation(self):
        arguments = self.operation_arguments
        if self.operation_name == "set_actor_location":
            return {"location": arguments.get("location")}
        if self.operation_name == "verify_actor_location":
            return {"location": arguments.get("expected_location")}
        if self.operation_name == "set_actor_rotation":
            return {"rotation": arguments.get("rotation")}
        if self.operation_name == "verify_actor_rotation":
            return {"rotation": arguments.get("expected_rotation")}
        if self.operation_name == "set_actor_scale":
            return {"scale": arguments.get("scale")}
        if self.operation_name == "verify_actor_scale":
            return {"scale": arguments.get("expected_scale")}
        if self.operation_name == "apply_material_variant":
            return {"material_variant": arguments.get("material_variant")}
        if self.operation_name == "verify_material_variant":
            return {"material_variant": arguments.get("expected_material_variant")}
        if self.operation_name == "apply_niagara_variant":
            return {"niagara_variant": arguments.get("niagara_variant")}
        if self.operation_name == "verify_niagara_variant":
            return {"niagara_variant": arguments.get("expected_niagara_variant")}
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
        if not isinstance(adapter, UnrealAdapterProduction):
            raise TypeError("adapter must be a UnrealAdapterProduction instance")
        self._adapter = adapter
        self._capabilities = UnrealCapabilityRegistry()

    _DISPATCH = {
        UnrealOperationKind.READ: "inspect",
        UnrealOperationKind.WRITE: "apply_authorized",
        UnrealOperationKind.VERIFY: "verify",
    }

    @staticmethod
    def _expected_verifier(write_operation):
        mapping = {
            "set_actor_location": "verify_actor_location",
            "set_actor_rotation": "verify_actor_rotation",
            "set_actor_scale": "verify_actor_scale",
            "apply_material_variant": "verify_material_variant",
            "apply_niagara_variant": "verify_niagara_variant",
        }
        return mapping.get(write_operation.name)

    @classmethod
    def _validate_execution_shape(cls, plan):
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
            expected_verifier = cls._expected_verifier(operation)
            if expected_verifier is not None and verification.name != expected_verifier:
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by '{expected_verifier}', not '{verification.name}'")

    @staticmethod
    def _format_preflight_error(exc):
        message = str(exc)
        if message == "location must contain exactly x, y, z":
            return "location must contain exactly x, y, and z"
        return message

    def _preflight_plan(self, plan):
        for index, operation in enumerate(plan.operations):
            try:
                self._capabilities.validate_operation(operation)
            except (KeyError, TypeError, ValueError) as exc:
                raise UnrealPlanExecutionError(f"Operation {index} ('{operation.name}') failed preflight: {self._format_preflight_error(exc)}") from exc

    @staticmethod
    def _verification_expectation(write_operation):
        arguments = write_operation.arguments
        if write_operation.name == "set_actor_location":
            return {"location": dict(arguments["location"])}
        if write_operation.name == "set_actor_rotation":
            return {"rotation": dict(arguments["rotation"])}
        if write_operation.name == "set_actor_scale":
            return {"scale": dict(arguments["scale"])}
        if write_operation.name == "apply_material_variant":
            return {"material_variant": dict(arguments["material_variant"])}
        if write_operation.name == "apply_niagara_variant":
            return {"niagara_variant": dict(arguments["niagara_variant"])}
        return {}

    @staticmethod
    def _is_semantically_verified(operation, evidence):
        return operation.name in {
            "verify_actor_location",
            "verify_actor_rotation",
            "verify_actor_scale",
            "verify_material_variant",
            "verify_niagara_variant",
        }

    def _execute_one(self, operation, authorization_id, *, expected_location=None, expected_rotation=None, expected_scale=None, expected_material_variant=None, expected_niagara_variant=None):
        arguments = dict(operation.arguments)
        arguments["entity_ids"] = tuple(operation.entity_ids)
        arguments["authorization_id"] = authorization_id
        validate_unreal_tool_call(operation.name, arguments)
        method_name = self._DISPATCH.get(operation.kind)
        if method_name is None:
            raise UnrealPlanExecutionError(f"No adapter endpoint for operation kind '{operation.kind.value}'")
        evidence = getattr(self._adapter, method_name)(operation, authorization_id)
        validate_evidence_for_operation(evidence, operation.name, tuple(operation.entity_ids))
        if operation.kind is UnrealOperationKind.VERIFY:
            if expected_location is not None: evidence = verify_actor_location(evidence, expected_location)
            if expected_rotation is not None: evidence = verify_actor_rotation(evidence, expected_rotation)
            if expected_scale is not None: evidence = verify_actor_scale(evidence, expected_scale)
            if expected_material_variant is not None: evidence = verify_material_variant(evidence, expected_material_variant)
            if expected_niagara_variant is not None: evidence = verify_niagara_variant(evidence, expected_niagara_variant)
            if self._is_semantically_verified(operation, evidence):
                evidence = replace(evidence, verified=True)
        return evidence

    @staticmethod
    def _failure_context(operation):
        return dict(operation.arguments)

    def execute_authorized(self, plan, authorization):
        if not isinstance(authorization, UnrealPlanAuthorization):
            raise TypeError("authorization must be a UnrealPlanAuthorization instance")
        if not authorization.matches(plan):
            raise UnrealPlanExecutionError("authorization receipt does not match the exact Unreal task plan")
        return self.execute(plan, authorization.authorization_id)

    def execute(self, plan, authorization_id):
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealPlanExecutionError("authorization_id must be a non-empty string")
        self._validate_execution_shape(plan)
        self._preflight_plan(plan)
        ledger = []
        completed = []
        for index, operation in enumerate(plan.operations):
            expected = {}
            if operation.kind is UnrealOperationKind.VERIFY:
                previous = plan.operations[index - 1] if index else None
                if previous is None or previous.kind not in (UnrealOperationKind.WRITE, UnrealOperationKind.READ):
                    raise UnrealPlanExecutionError(f"Verify operation {index} ('{operation.name}') must follow a read or write")
                if previous.kind is UnrealOperationKind.WRITE:
                    expected = self._verification_expectation(previous)
            try:
                evidence = self._execute_one(operation, authorization_id, expected_location=expected.get("location"), expected_rotation=expected.get("rotation"), expected_scale=expected.get("scale"), expected_material_variant=expected.get("material_variant"), expected_niagara_variant=expected.get("niagara_variant"))
            except (UnrealAdapterError, ValueError, TypeError) as exc:
                message = f"Operation {index} ('{operation.name}') failed: {exc}"
                failure = UnrealPlanExecutionFailure(plan.intent_id, index, operation.name, tuple(ledger), message, tuple(operation.entity_ids), self._failure_context(operation), tuple(completed))
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except Exception as exc:
                message = f"Unexpected execution failure for operation {index} ('{operation.name}'):\n{exc}"
                failure = UnrealPlanExecutionFailure(plan.intent_id, index, operation.name, tuple(ledger), message, tuple(operation.entity_ids), self._failure_context(operation), tuple(completed))
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            ledger.append(evidence)
            completed.append(self._failure_context(operation))
        return UnrealPlanExecutionResult(plan.intent_id, tuple(ledger), True)
