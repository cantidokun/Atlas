"""Deterministic executor for Unreal task plans.

Bridges ``UnrealTaskPlan`` and ``UnrealAdapterProduction`` by dispatching each
operation to the correct adapter endpoint based on its ``kind``, collecting
validated evidence, and returning the complete ledger.

Execution is fail-closed: any adapter or validation error aborts immediately.
"""

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Tuple

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation
from planning.unreal_state_verifier import verify_actor_location
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_tool_schema import validate_unreal_tool_call


@dataclass(frozen=True)
class UnrealPlanExecutionFailure:
    """Structured context for a failed plan execution.

    ``operation_arguments`` preserves the exact caller-supplied operation
    payload at the failure boundary. ``completed_operation_arguments`` keeps
    the same payload history for operations that already succeeded. This is
    critical when a post-write verification fails: the failed VERIFY operation
    has no mutation payload, but recovery still needs the original write intent
    to determine what fresh state must be compared against.

    These fields are context only. They are never authorization receipts and
    cannot authorize a retry.
    """

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
        object.__setattr__(
            self,
            "completed_operation_arguments",
            tuple(dict(arguments) for arguments in self.completed_operation_arguments),
        )


class UnrealPlanExecutionError(RuntimeError):
    """Raised when plan execution cannot continue.

    The exception preserves the completed evidence ledger and the exact
    operation boundary at which execution stopped. This allows a caller to
    distinguish partial execution from a plan that never reached Unreal and
    provides the facts required by a future recovery policy.
    """

    def __init__(self, message: str, *, failure: Optional[UnrealPlanExecutionFailure] = None):
        super().__init__(message)
        self.failure = failure


@dataclass(frozen=True)
class UnrealPlanExecutionResult:
    """Immutable result of executing a complete Unreal task plan."""

    intent_id: str
    evidence_ledger: Tuple[UnrealEvidence, ...]
    success: bool


class UnrealPlanExecutor:
    """Execute every operation in a ``UnrealTaskPlan`` deterministically.

    Each operation is dispatched to the adapter endpoint that matches its
    ``kind``. Evidence returned by the adapter is validated against the
    originating operation before being appended to the ledger.

    Every mutation is required to be immediately followed by a verification
    operation for the same explicit targets. This prevents a write from being
    reported as a successful production execution without a post-write proof
    step.

    The executor does **not** issue or verify authorization — it only
    transmits the caller-supplied ``authorization_id``.
    """

    def __init__(self, adapter: UnrealAdapterProduction) -> None:
        if not isinstance(adapter, UnrealAdapterProduction):
            raise TypeError("adapter must be an UnrealAdapterProduction instance")
        self._adapter = adapter

    _DISPATCH = {
        UnrealOperationKind.READ: "inspect",
        UnrealOperationKind.WRITE: "apply_authorized",
        UnrealOperationKind.VERIFY: "verify",
    }

    @staticmethod
    def _validate_execution_shape(plan: UnrealTaskPlan) -> None:
        """Require every write to have an adjacent verification boundary."""
        operations = plan.operations
        for index, operation in enumerate(operations):
            if operation.kind is not UnrealOperationKind.WRITE:
                continue
            if index + 1 >= len(operations):
                raise UnrealPlanExecutionError(
                    f"Write operation {index} ('{operation.name}') must be followed by verification"
                )
            verification = operations[index + 1]
            if verification.kind is not UnrealOperationKind.VERIFY:
                raise UnrealPlanExecutionError(
                    f"Write operation {index} ('{operation.name}') must be immediately followed by verification"
                )
            if tuple(verification.entity_ids) != tuple(operation.entity_ids):
                raise UnrealPlanExecutionError(
                    f"Write operation {index} ('{operation.name}') and verification must target the same entities"
                )

    def _execute_one(
        self,
        operation: UnrealOperation,
        authorization_id: str,
        expected_location: Optional[dict] = None,
    ) -> UnrealEvidence:
        arguments = dict(operation.arguments)
        arguments["entity_ids"] = tuple(operation.entity_ids)
        arguments["authorization_id"] = authorization_id
        validate_unreal_tool_call(operation.name, arguments)

        method_name = self._DISPATCH.get(operation.kind)
        if method_name is None:
            raise UnrealPlanExecutionError(
                f"No adapter endpoint for operation kind '{operation.kind.value}'"
            )
        method = getattr(self._adapter, method_name)
        evidence: UnrealEvidence = method(operation, authorization_id)

        validate_evidence_for_operation(
            evidence,
            operation.name,
            tuple(operation.entity_ids),
        )

        if operation.kind is UnrealOperationKind.VERIFY and expected_location is not None:
            verify_actor_location(evidence, expected_location)

        return evidence

    @staticmethod
    def _failure_context(operation: UnrealOperation) -> Mapping[str, Any]:
        """Capture operation arguments without the transport-only auth field."""
        return dict(operation.arguments)

    def execute(
        self,
        plan: UnrealTaskPlan,
        authorization_id: str,
    ) -> UnrealPlanExecutionResult:
        """Execute *plan* in strict order and return the evidence ledger."""
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealPlanExecutionError("authorization_id must be a non-empty string")

        self._validate_execution_shape(plan)

        ledger: List[UnrealEvidence] = []
        completed_operation_arguments: List[Mapping[str, Any]] = []
        expected_location: Optional[dict] = None

        for index, operation in enumerate(plan.operations):
            if operation.name == "set_actor_location":
                expected_location = dict(operation.arguments["location"])

            try:
                evidence = self._execute_one(
                    operation,
                    authorization_id,
                    expected_location if operation.kind is UnrealOperationKind.VERIFY else None,
                )
            except UnrealAdapterError as exc:
                message = f"Operation {index} ('{operation.name}') failed: {exc}"
                failure = UnrealPlanExecutionFailure(
                    intent_id=plan.intent_id,
                    operation_index=index,
                    operation_name=operation.name,
                    completed_evidence=tuple(ledger),
                    error=message,
                    operation_entity_ids=tuple(operation.entity_ids),
                    operation_arguments=self._failure_context(operation),
                    completed_operation_arguments=tuple(completed_operation_arguments),
                )
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except ValueError as exc:
                message = (
                    f"Evidence/tool validation failed for operation {index} "
                    f"('{operation.name}'): {exc}"
                )
                failure = UnrealPlanExecutionFailure(
                    intent_id=plan.intent_id,
                    operation_index=index,
                    operation_name=operation.name,
                    completed_evidence=tuple(ledger),
                    error=message,
                    operation_entity_ids=tuple(operation.entity_ids),
                    operation_arguments=self._failure_context(operation),
                    completed_operation_arguments=tuple(completed_operation_arguments),
                )
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except TypeError as exc:
                message = (
                    f"Tool argument validation failed for operation {index} "
                    f"('{operation.name}'): {exc}"
                )
                failure = UnrealPlanExecutionFailure(
                    intent_id=plan.intent_id,
                    operation_index=index,
                    operation_name=operation.name,
                    completed_evidence=tuple(ledger),
                    error=message,
                    operation_entity_ids=tuple(operation.entity_ids),
                    operation_arguments=self._failure_context(operation),
                    completed_operation_arguments=tuple(completed_operation_arguments),
                )
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            except Exception as exc:
                # Preserve the same structured failure boundary for unexpected
                # adapter/runtime errors. Recovery can then fail closed using
                # the exact operation and completed evidence instead of losing
                # the execution context to an unclassified exception.
                message = (
                    f"Unexpected execution failure for operation {index} "
                    f"('{operation.name}'): {exc}"
                )
                failure = UnrealPlanExecutionFailure(
                    intent_id=plan.intent_id,
                    operation_index=index,
                    operation_name=operation.name,
                    completed_evidence=tuple(ledger),
                    error=message,
                    operation_entity_ids=tuple(operation.entity_ids),
                    operation_arguments=self._failure_context(operation),
                    completed_operation_arguments=tuple(completed_operation_arguments),
                )
                raise UnrealPlanExecutionError(message, failure=failure) from exc
            ledger.append(evidence)
            completed_operation_arguments.append(self._failure_context(operation))

        return UnrealPlanExecutionResult(
            intent_id=plan.intent_id,
            evidence_ledger=tuple(ledger),
            success=True,
        )
