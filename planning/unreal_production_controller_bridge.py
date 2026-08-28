"""Controller-facing bridge for heterogeneous Unreal production transactions.

This module deliberately does not replace the existing ControllerRuntime.
Instead it gives higher-level callers a deterministic production transaction
boundary while preserving the existing authorization and recovery layers.
"""

from dataclasses import dataclass
from typing import Optional

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_production_executor import UnrealProductionExecutionResult, UnrealProductionExecutor
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_production_recovery import UnrealProductionRecoveryAssessment
from planning.unreal_production_recovery_adapter import UnrealProductionReceiptRecovery, prepare_production_receipt_recovery


@dataclass(frozen=True)
class UnrealProductionControllerState:
    """Durable controller snapshot for one production transaction."""

    phase: str
    status: str
    failure: Optional[UnrealPlanExecutionFailure]
    recovery_assessment: Optional[UnrealProductionRecoveryAssessment]


class UnrealProductionControllerBridge:
    """Expose production execution as a deterministic controller boundary."""

    def __init__(self, executor: UnrealPlanExecutor) -> None:
        if not isinstance(executor, UnrealPlanExecutor):
            raise TypeError("executor must be a UnrealPlanExecutor instance")
        self._production_executor = UnrealProductionExecutor(executor)
        self._executor = executor
        self.state = UnrealProductionControllerState(
            phase="not_started",
            status="idle",
            failure=None,
            recovery_assessment=None,
        )

    def start(
        self,
        production: UnrealProductionPlan,
        authorization: UnrealPlanAuthorization,
        *,
        reassessment_authorization: Optional[UnrealPlanAuthorization] = None,
        replacement_authorization: Optional[UnrealPlanAuthorization] = None,
    ) -> UnrealProductionExecutionResult:
        result = self._production_executor.execute(
            production,
            authorization,
            reassessment_authorization=reassessment_authorization,
            replacement_authorization=replacement_authorization,
        )
        if result.initial_result is not None:
            phase = "complete"
            status = "complete"
        elif result.recovery is not None:
            phase = "recovery_complete"
            status = "complete" if result.success else result.recovery.assessment.disposition
        else:
            phase = self._failed_phase(production, result.failure)
            status = "failed_pending_recovery"
        self.state = UnrealProductionControllerState(
            phase=phase,
            status=status,
            failure=result.failure,
            recovery_assessment=None if result.recovery is None else result.recovery.assessment,
        )
        return result

    def prepare_recovery(
        self,
        production: UnrealProductionPlan,
        failure: UnrealPlanExecutionFailure,
        reassessment_authorization: UnrealPlanAuthorization,
        replacement_authorization: Optional[UnrealPlanAuthorization] = None,
    ) -> UnrealProductionReceiptRecovery:
        prepared = prepare_production_receipt_recovery(
            self._executor,
            production,
            failure,
            reassessment_authorization,
            replacement_authorization,
        )
        phase = "recovery_reassessed"
        status = prepared.assessment.disposition
        self.state = UnrealProductionControllerState(
            phase=phase,
            status=status,
            failure=failure,
            recovery_assessment=prepared.assessment,
        )
        return prepared

    @staticmethod
    def _failed_phase(
        production: UnrealProductionPlan,
        failure: Optional[UnrealPlanExecutionFailure],
    ) -> str:
        if failure is None:
            return "unknown"
        for phase_name, start, end in production.phases:
            if start <= failure.operation_index < end:
                return phase_name
        return "unknown"
