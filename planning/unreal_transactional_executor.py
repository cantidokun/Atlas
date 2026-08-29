"""Transactional Unreal executor backed by an immutable production ledger."""

from dataclasses import dataclass

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_production_transaction_ledger import UnrealProductionTransactionLedger
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_agent import UnrealOperationKind


@dataclass(frozen=True)
class UnrealTransactionalExecutionResult(UnrealPlanExecutionResult):
    """Successful execution result with its immutable transaction ledger."""

    transaction_ledger: UnrealProductionTransactionLedger = None


class UnrealTransactionalPlanExecutor(UnrealPlanExecutor):
    """Execute an authorized Unreal plan with explicit transaction bookkeeping."""

    def execute_authorized(self, plan: UnrealTaskPlan, authorization: UnrealPlanAuthorization):
        if not isinstance(authorization, UnrealPlanAuthorization):
            raise TypeError("authorization must be a UnrealPlanAuthorization instance")
        if not authorization.matches(plan):
            raise UnrealPlanExecutionError("authorization receipt does not match the exact Unreal task plan")
        return self.execute(plan, authorization.authorization_id)

    @staticmethod
    def _raise_transaction_failure(message, failure, ledger):
        error = UnrealPlanExecutionError(message, failure=failure)
        error.transaction_ledger = ledger
        raise error

    def execute(self, plan: UnrealTaskPlan, authorization_id: str):
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealPlanExecutionError("authorization_id must be a non-empty string")

        self._validate_execution_shape(plan)
        self._preflight_plan(plan)
        ledger = UnrealProductionTransactionLedger(plan.intent_id)
        evidence_ledger = []
        completed_arguments = []

        for index, operation in enumerate(plan.operations):
            expected = {}
            if operation.kind is UnrealOperationKind.VERIFY:
                previous = plan.operations[index - 1] if index else None
                if previous is None or previous.kind not in (UnrealOperationKind.WRITE, UnrealOperationKind.READ):
                    raise UnrealPlanExecutionError(f"Verify operation {index} ('{operation.name}') must follow a read or write")
                if previous.kind is UnrealOperationKind.WRITE:
                    expected = self._verification_expectation(previous)
            try:
                evidence = self._execute_one(
                    operation, authorization_id,
                    expected_location=expected.get("location"), expected_rotation=expected.get("rotation"),
                    expected_scale=expected.get("scale"), expected_material_variant=expected.get("material_variant"),
                    expected_niagara_variant=expected.get("niagara_variant"), expected_start_frame=expected.get("start_frame"),
                    expected_end_frame=expected.get("end_frame"),
                )
            except (UnrealPlanExecutionError, UnrealPlanExecutionFailure) as exc:
                frozen = ledger.record_failure(index, operation.name, tuple(operation.entity_ids), dict(operation.arguments))
                failure = exc.failure if isinstance(exc, UnrealPlanExecutionError) and exc.failure is not None else UnrealPlanExecutionFailure(
                    plan.intent_id, index, operation.name, tuple(evidence_ledger), str(exc),
                    tuple(operation.entity_ids), dict(operation.arguments), tuple(completed_arguments),
                )
                self._raise_transaction_failure(str(exc), failure, frozen)
            except Exception as exc:
                frozen = ledger.record_failure(index, operation.name, tuple(operation.entity_ids), dict(operation.arguments))
                failure = UnrealPlanExecutionFailure(
                    plan.intent_id, index, operation.name, tuple(evidence_ledger),
                    f"Operation {index} ('{operation.name}') failed: {exc}",
                    tuple(operation.entity_ids), dict(operation.arguments), tuple(completed_arguments),
                )
                self._raise_transaction_failure(failure.error, failure, frozen)

            evidence_ledger.append(evidence)
            completed_arguments.append(dict(operation.arguments))
            ledger = ledger.record_success(index, operation.name, tuple(operation.entity_ids), dict(operation.arguments), len(evidence_ledger) - 1)

        return UnrealTransactionalExecutionResult(plan.intent_id, tuple(evidence_ledger), True, ledger)
