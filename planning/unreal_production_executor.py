"""Higher-level execution boundary for heterogeneous Unreal production transactions.

This layer is intentionally thin: it owns transaction-level control flow, while
planning, exact authorization, execution, evidence, and production-aware
recovery remain in their existing boundaries.
"""

from dataclasses import dataclass
from typing import Optional

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import (
    UnrealPlanExecutionError,
    UnrealPlanExecutionFailure,
    UnrealPlanExecutionResult,
    UnrealPlanExecutor,
)
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_production_recovery import (
    UnrealProductionRecoveryResult,
    execute_production_recovery,
)


@dataclass(frozen=True)
class UnrealProductionExecutionResult:
    """Complete outcome of one production transaction attempt."""

    production: UnrealProductionPlan
    initial_result: Optional[UnrealPlanExecutionResult]
    failure: Optional[UnrealPlanExecutionFailure]
    recovery: Optional[UnrealProductionRecoveryResult]

    @property
    def success(self) -> bool:
        if self.initial_result is not None:
            return self.initial_result.success
        return bool(
            self.recovery is not None
            and self.recovery.replacement_result is not None
            and self.recovery.replacement_result.success
        )


class UnrealProductionExecutor:
    """Execute a production plan and optionally drive its explicit recovery path."""

    def __init__(self, executor: UnrealPlanExecutor) -> None:
        if not isinstance(executor, UnrealPlanExecutor):
            raise TypeError("executor must be a UnrealPlanExecutor instance")
        self._executor = executor

    def execute(
        self,
        production: UnrealProductionPlan,
        authorization: UnrealPlanAuthorization,
        *,
        reassessment_authorization: Optional[UnrealPlanAuthorization] = None,
        replacement_authorization: Optional[UnrealPlanAuthorization] = None,
    ) -> UnrealProductionExecutionResult:
        """Execute one exact production transaction and, on failure, recover explicitly.

        Authorization is never generated here. The caller must authorize the
        original production plan and, if recovery is required, separately
        authorize the exact reassessment and replacement plans.
        """
        if not isinstance(production, UnrealProductionPlan):
            raise TypeError("production must be an UnrealProductionPlan instance")
        if not isinstance(authorization, UnrealPlanAuthorization):
            raise TypeError("authorization must be a UnrealPlanAuthorization instance")
        if not authorization.matches(production.plan):
            raise ValueError("production authorization does not match the exact production plan")
        if replacement_authorization is not None and reassessment_authorization is None:
            raise ValueError("replacement authorization requires reassessment authorization")

        try:
            initial_result = self._executor.execute_authorized(production.plan, authorization)
        except UnrealPlanExecutionError as exc:
            failure = exc.failure
            if failure is None:
                raise
            if reassessment_authorization is None:
                return UnrealProductionExecutionResult(
                    production=production,
                    initial_result=None,
                    failure=failure,
                    recovery=None,
                )

            recovery = execute_production_recovery(
                self._executor,
                production,
                failure,
                reassessment_authorization,
                replacement_authorization,
            )
            return UnrealProductionExecutionResult(
                production=production,
                initial_result=None,
                failure=failure,
                recovery=recovery,
            )

        if reassessment_authorization is not None or replacement_authorization is not None:
            raise ValueError("recovery authorization cannot be supplied when the production transaction succeeds")

        return UnrealProductionExecutionResult(
            production=production,
            initial_result=initial_result,
            failure=None,
            recovery=None,
        )
