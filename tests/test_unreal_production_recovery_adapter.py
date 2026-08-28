"""Tests for bridging production recovery into the canonical receipt workflow."""

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor, UnrealPlanExecutionError
from planning.unreal_production_recovery import build_production_reassessment_plan, build_production_replacement_plan, assess_production_reassessment
from planning.unreal_production_recovery_adapter import (
    prepare_production_receipt_recovery,
    execute_prepared_production_receipt_recovery,
)
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def test_receipt_bridge_prepares_exact_reassessment_and_replacement_identity():
    production = __import__('planning.unreal_production_operation', fromlist=['build_unreal_production_plan']).build_unreal_production_plan(_intent(), _spec())
    transport = ProductionTransport(fail_at=20)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "production-receipt-bridge-test"))
    original_auth = UnrealPlanAuthorization.issue(production.plan, "production-auth")

    try:
        executor.execute_authorized(production.plan, original_auth)
    except UnrealPlanExecutionError as exc:
        failure = exc.failure
    else:
        raise AssertionError("expected injected production failure")

    reassessment_plan = build_production_reassessment_plan(production, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    transport.fail_at = 999
    transport.calls.clear()

    prepared = prepare_production_receipt_recovery(
        executor, production, failure, reassessment_auth,
    )

    # The prepared path sees the reset state and therefore requires a replacement.
    assert prepared.assessment.disposition == "replacement_required"
    assert prepared.replacement_plan is not None
    assert prepared.recovery_receipt is None  # replacement authorization is intentionally required first


def test_receipt_bridge_requires_replacement_authorization_for_mismatch():
    production = __import__('planning.unreal_production_operation', fromlist=['build_unreal_production_plan']).build_unreal_production_plan(_intent(), _spec())
    transport = ProductionTransport(fail_at=20)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "production-receipt-bridge-required-auth-test"))
    original_auth = UnrealPlanAuthorization.issue(production.plan, "production-auth")

    try:
        executor.execute_authorized(production.plan, original_auth)
    except UnrealPlanExecutionError as exc:
        failure = exc.failure
    else:
        raise AssertionError("expected injected production failure")

    reassessment_plan = build_production_reassessment_plan(production, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    transport.fail_at = 999
    transport.calls.clear()

    prepared = prepare_production_receipt_recovery(
        executor, production, failure, reassessment_auth,
    )

    assert prepared.recovery_receipt is None
