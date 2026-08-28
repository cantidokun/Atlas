"""Tests for the runtime-facing Unreal production integration boundary."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_bridge import UnrealProductionControllerBridge
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_recovery import build_production_reassessment_plan, issue_production_replacement_authorization
from planning.unreal_production_runtime_integration import UnrealProductionRuntimeIntegration
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _production():
    return build_unreal_production_plan(_intent(), _spec())


def _integration(transport):
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "production-runtime-integration-test"))
    return UnrealProductionRuntimeIntegration(UnrealProductionControllerBridge(executor))


def test_runtime_integration_starts_and_completes_authorized_transaction():
    production = _production()
    authorized = authorize_production_plan(production, "production-auth")
    runtime = _integration(ProductionTransport())

    outcome = runtime.start(authorized)

    assert outcome.state == "complete"
    assert runtime.active is False
    assert runtime.complete is True
    assert runtime.snapshot.state == "complete"
    assert runtime.snapshot.phase == "complete"


def test_runtime_integration_exposes_recovery_boundary_without_authorizing_it():
    production = _production()
    authorized = authorize_production_plan(production, "production-auth")
    runtime = _integration(ProductionTransport(fail_at=20))

    outcome = runtime.start(authorized)

    assert outcome.state == "awaiting_reassessment"
    assert runtime.active is True
    assert runtime.complete is False
    assert runtime.snapshot.waiting_for_reassessment is True
    assert runtime.snapshot.waiting_for_replacement is False
    assert runtime.snapshot.failure is not None


def test_runtime_integration_drives_reassessment_then_exact_replacement():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    runtime = _integration(transport)
    authorized = authorize_production_plan(production, "production-auth")
    started = runtime.start(authorized)
    assert started.failure is not None

    reassessment_plan = build_production_reassessment_plan(production, started.failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    reassessed = runtime.reassess(reassessment_auth)

    assert reassessed.state == "awaiting_replacement"
    assert runtime.snapshot.waiting_for_reassessment is False
    assert runtime.snapshot.waiting_for_replacement is True
    assert reassessed.recovery is not None
    assert reassessed.recovery.replacement_plan is not None

    replacement_auth = issue_production_replacement_authorization(
        reassessed.recovery.replacement_plan,
        "replacement-auth",
    )
    transport.fail_at = 999
    completed = runtime.resume_recovery(replacement_auth)

    assert completed.state == "recovery_complete"
    assert runtime.active is False
    assert runtime.complete is True
    assert runtime.snapshot.state == "recovery_complete"


def test_runtime_integration_requires_failure_before_recovery():
    runtime = _integration(ProductionTransport())

    with pytest.raises(RuntimeError, match="no failed production transaction"):
        runtime.require_active_failure()
