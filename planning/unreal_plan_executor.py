"""Deterministic executor for Unreal task plans.

Bridges ``UnrealTaskPlan`` and ``UnrealAdapterProduction`` by dispatching each
operation to the correct adapter endpoint based on its ``kind``, collecting
validated evidence, and returning the complete ledger.

Execution is fail-closed: any adapter or validation error aborts immediately.
"""

from dataclasses import dataclass
from typing import List, Tuple

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence, validate_evidence_for_operation
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_tool_schema import validate_unreal_tool_call


class UnrealPlanExecutionError(RuntimeError):
    """Raised when plan execution cannot continue."""


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

    def _execute_one(
        self,
        operation: UnrealOperation,
        authorization_id: str,
    ) -> UnrealEvidence:
        # Validate the complete operation payload before dispatching. The
        # operation arguments are preserved so mutation-specific schemas (for
        # example set_actor_location.location) cannot be bypassed by the
        # executor.
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
        return evidence

    def execute(
        self,
        plan: UnrealTaskPlan,
        authorization_id: str,
    ) -> UnrealPlanExecutionResult:
        """Execute *plan* in strict order and return the evidence ledger.

        Parameters
        ----------
        plan:
            A validated ``UnrealTaskPlan`` produced by ``UnrealTaskPlanner``.
        authorization_id:
            The Atlas authorization receipt ID that covers this plan.

        Raises
        ------
        UnrealPlanExecutionError
            If any operation fails or evidence validation rejects a result.
        """
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealPlanExecutionError("authorization_id must be a non-empty string")

        ledger: List[UnrealEvidence] = []

        for index, operation in enumerate(plan.operations):
            try:
                evidence = self._execute_one(operation, authorization_id)
            except UnrealAdapterError as exc:
                raise UnrealPlanExecutionError(
                    f"Operation {index} ('{operation.name}') failed: {exc}"
                ) from exc
            except ValueError as exc:
                raise UnrealPlanExecutionError(
                    f"Evidence/tool validation failed for operation {index} "
                    f"('{operation.name}'): {exc}"
                ) from exc
            except TypeError as exc:
                raise UnrealPlanExecutionError(
                    f"Tool argument validation failed for operation {index} "
                    f"('{operation.name}'): {exc}"
                ) from exc
            ledger.append(evidence)

        return UnrealPlanExecutionResult(
            intent_id=plan.intent_id,
            evidence_ledger=tuple(ledger),
            success=True,
        )
