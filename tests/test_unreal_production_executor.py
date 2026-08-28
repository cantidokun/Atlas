"""Transaction-level tests for heterogeneous Unreal production execution."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_recovery import (
    assess_production_reassessment,
    build_production_reassessment_plan,
    build_production_replacement_plan,
    issue_production_replacement_authorization,
)
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _production():
    from planning.unreal_production_operation import build_unreal_production_plan
    return build_unreal_production_plan(_intent(), _spec())


def test_successful_transaction_is_executed_as_one_authorized_boundary():
    production = _production()
    transport = ProductionTransport()
    executor = UnrealProductionExecutor(
        UnrealPlanExecutor(UnrealAdapterProduction(transport, "production-transaction-test"))
    )
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")

    result = executor.execute(production, authorization)

    assert result.success is True
    assert result.failure is None
    assert result.recovery is None
    assert result.initial_result is not None
    assert result.initial_result.success is True


def test_failed_transaction_can_drive_fresh_reassessment_and_authorized_replacement():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    raw_executor = UnrealPlanExecutor(
        UnrealAdapterProduction(transport, "production-transaction-recovery-test")
    )
    executor = UnrealProductionExecutor(raw_executor)
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")

    # Derive the exact recovery authorizations from the same failure boundary
    # the transaction executor will encounter, without executing the mutation
    # a second time.
    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        raw_executor.execute_authorized(production.plan, authorization)
    failure = exc_info.value.failure
    assert failure is not None

    reassessment_plan = build_production_reassessment_plan(production, failure)
    reassessment_authorization = UnrealPlanAuthorization.issue(
        reassessment_plan, "reassessment-auth"
    )
    reassessment_result = raw_executor.execute_authorized(
        reassessment_plan, reassessment_authorization
    )
    assessment = assess_production_reassessment(production, failure, reassessment_result)
    replacement_plan = build_production_replacement_plan(production, assessment)
    replacement_authorization = issue_production_replacement_authorization(
        replacement_plan, "replacement-auth"
    )

    # Reset the injected transport boundary so the transaction executor can
    # perform the actual production attempt and recovery sequence from scratch.
    transport.fail_at = 999
    transport.calls.clear()
    transport.state["FIELD_SURFACE"]["render"] = {
        "width": 640,
        "height": 360,
        "start_frame": 0,
        "end_frame": 0,
        "output_directory": "Saved/Default",
        "output_format": "png",
    }
    transport.state["FIELD_SURFACE"]["sequencer"] = {
        "playback_range": {"start_frame": 0, "end_frame": 0}
    }

    # Reintroduce the failure only for the transaction's initial execution.
    transport.fail_at = 20
    result = executor.execute(
        production,
        authorization,
        reassessment_authorization=reassessment_authorization,
        replacement_authorization=replacement_authorization,
    )

    assert result.failure is not None
    assert result.recovery is not None
    assert result.recovery.assessment.disposition == "replacement_required"
    assert result.recovery.replacement_result is not None
    assert result.recovery.replacement_result.success is True
    assert result.success is True
    assert transport.state["FIELD_SURFACE"]["render"]["width"] == 1280


def test_transaction_rejects_authorization_for_a_different_production_plan():
    production = _production()
    other = _production()
    authorization = UnrealPlanAuthorization.issue(other.plan, "wrong-plan-auth")
    executor = UnrealProductionExecutor(
        UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "auth-boundary-test"))
    )

    with pytest.raises(ValueError, match="exact production plan"):
        executor.execute(production, authorization)


def test_transaction_does_not_accept_recovery_authorization_on_success():
    production = _production()
    transport = ProductionTransport()
    raw_executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "success-auth-test"))
    executor = UnrealProductionExecutor(raw_executor)
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")
    reassessment = build_production_reassessment_plan(
        production,
        # This failure object is intentionally obtained without relying on a
        # successful transaction; use a known production boundary fixture.
        _failure_for_boundary(raw_executor, production, authorization),
    )
    reassessment_authorization = UnrealPlanAuthorization.issue(reassessment, "unused-reassessment-auth")

    with pytest.raises(ValueError, match="recovery authorization cannot"):
        executor.execute(
            production,
            authorization,
            reassessment_authorization=reassessment_authorization,
        )


def _failure_for_boundary(raw_executor, production, authorization):
    transport = raw_executor._adapter._transport
    transport.fail_at = 20
    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        raw_executor.execute_authorized(production.plan, authorization)
    failure = exc_info.value.failure
    assert failure is not None
    transport.fail_at = 999
    transport.calls.clear()
    return failure
