"""Focused tests for the production-aware controller bridge."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_bridge import UnrealProductionControllerBridge
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_recovery import (
    assess_production_reassessment,
    build_production_reassessment_plan,
    build_production_replacement_plan,
    issue_production_replacement_authorization,
)
from planning.unreal_transactional_executor import UnrealTransactionalExecutionResult
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _production():
    return build_unreal_production_plan(_intent(), _spec())


def test_controller_bridge_starts_and_completes_successful_transaction():
    production = _production()
    transport = ProductionTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "controller-bridge-test"))
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")
    bridge = UnrealProductionControllerBridge(executor)

    started = bridge.start(production, authorization)
    assert started.state == "complete"
    assert started.result is not None
    assert started.result.success is True
    assert isinstance(started.result.initial_result, UnrealTransactionalExecutionResult)
    assert started.result.initial_result.transaction_ledger.terminal is True
    assert bridge.complete is True


def test_controller_bridge_records_failed_transaction_and_accepts_explicit_recovery_artifacts():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "controller-bridge-recovery-test"))
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")
    bridge = UnrealProductionControllerBridge(executor)

    started = bridge.start(production, authorization)
    assert started.state == "failed_pending_recovery"
    assert started.failure is not None
    assert bridge.complete is False

    failure = started.failure
    assert failure.operation_index == 20
    reassessment_plan = build_production_reassessment_plan(production, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    transport.fail_at = 999
    transport.calls.clear()
    reassessment_result = executor.execute_authorized(reassessment_plan, reassessment_auth)
    assessment = assess_production_reassessment(production, failure, reassessment_result)
    replacement_plan = build_production_replacement_plan(production, assessment)
    replacement_auth = issue_production_replacement_authorization(replacement_plan, "replacement-auth")

    completed = bridge.recover(
        reassessment_authorization=reassessment_auth,
        replacement_authorization=replacement_auth,
    )

    assert completed.state == "recovery_complete"
    assert completed.recovery is not None
    assert completed.recovery.replacement_result is not None
    assert isinstance(completed.recovery.replacement_result, UnrealTransactionalExecutionResult)
    assert completed.recovery.replacement_result.success is True
    assert completed.recovery.replacement_result.transaction_ledger.terminal is True
    assert bridge.complete is True


def test_controller_bridge_refuses_recovery_before_a_failed_transaction():
    production = _production()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "controller-bridge-invalid-test"))
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")
    bridge = UnrealProductionControllerBridge(executor)

    with pytest.raises(RuntimeError, match="no failed production transaction"):
        bridge.recover(
            reassessment_authorization=UnrealPlanAuthorization.issue(
                production.plan, "wrong-reassessment-auth"
            )
        )
