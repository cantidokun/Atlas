"""Integration coverage for production recovery through the ledger-backed executor."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_recovery import (
    build_production_reassessment_plan,
    build_production_replacement_plan,
    execute_production_recovery,
)
from planning.unreal_production_transaction_ledger import UnrealProductionTransactionLedger
from planning.unreal_transactional_executor import UnrealTransactionalPlanExecutor
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def test_transactional_executor_carries_terminal_ledger_through_recovery():
    production = build_unreal_production_plan(_intent(), _spec())
    transport = ProductionTransport(fail_at=20)
    executor = UnrealTransactionalPlanExecutor(UnrealAdapterProduction(transport, "transactional-recovery-test"))

    with pytest.raises(UnrealPlanExecutionError) as raised:
        executor.execute(production.plan, "production-auth")

    failure = raised.value.failure
    ledger = raised.value.transaction_ledger
    assert failure is not None
    assert isinstance(ledger, UnrealProductionTransactionLedger)
    assert ledger.terminal is True
    assert ledger.failed_operation_index == failure.operation_index
    assert ledger.failed_operation_name == failure.operation_name
    assert dict(ledger.failed_arguments) == dict(failure.operation_arguments)
    assert ledger.completed_operation_indices == tuple(range(failure.operation_index))

    reassessment = build_production_reassessment_plan(production, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "transactional-reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assert isinstance(reassessment_result.transaction_ledger, UnrealProductionTransactionLedger)
    assert reassessment_result.transaction_ledger.terminal is False

    recovery_assessment = __import__(
        "planning.unreal_production_recovery", fromlist=["assess_production_reassessment"]
    ).assess_production_reassessment(production, failure, reassessment_result)
    replacement_plan = build_production_replacement_plan(production, recovery_assessment)
    replacement_auth = UnrealPlanAuthorization.issue(replacement_plan, "transactional-replacement-auth")

    recovery = execute_production_recovery(
        executor,
        production,
        failure,
        reassessment_auth,
        replacement_auth,
    )

    assert recovery.replacement_result is not None
    assert isinstance(recovery.replacement_result.transaction_ledger, UnrealProductionTransactionLedger)
    assert recovery.replacement_result.transaction_ledger.terminal is False
    assert recovery.replacement_result.transaction_ledger.completed_operation_indices == (0, 1)
