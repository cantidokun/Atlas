"""Tests for the generic-runtime-facing Unreal production adapter."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_recovery import build_production_reassessment_plan, issue_production_replacement_authorization
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _production():
    return build_unreal_production_plan(_intent(), _spec())


def test_runtime_adapter_completes_successful_authorized_production():
    production = _production()
    authorized = authorize_production_plan(production, "production-auth")
    adapter = UnrealProductionRuntimeAdapter(
        UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "runtime-adapter-test"))
    )

    snapshot = adapter.start(authorized)

    assert snapshot.state == "complete"
    assert snapshot.phase == "complete"
    assert snapshot.waiting_for_reassessment is False
    assert snapshot.waiting_for_replacement is False
    assert snapshot.required_authorizations == ()
    assert adapter.complete is True


def test_runtime_adapter_exposes_reassessment_boundary_without_authorizing_it():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    adapter = UnrealProductionRuntimeAdapter(
        UnrealPlanExecutor(UnrealAdapterProduction(transport, "runtime-adapter-recovery-test"))
    )
    authorized = authorize_production_plan(production, "production-auth")

    failed = adapter.start(authorized)
    assert failed.state == "awaiting_reassessment"
    assert failed.waiting_for_reassessment is True
    assert failed.required_authorizations == ("reassessment",)

    with pytest.raises(RuntimeError, match="not waiting for replacement"):
        adapter.resume(UnrealPlanAuthorization.issue(production.plan, "invalid-replacement-auth"))


def test_runtime_adapter_reassesses_and_then_resumes_with_exact_replacement():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    adapter = UnrealProductionRuntimeAdapter(
        UnrealPlanExecutor(UnrealAdapterProduction(transport, "runtime-adapter-resume-test"))
    )
    authorized = authorize_production_plan(production, "production-auth")
    failed = adapter.start(authorized)
    assert failed.failure is not None

    reassessment_plan = build_production_reassessment_plan(production, failed.failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    reassessed = adapter.reassess(reassessment_auth)

    assert reassessed.state == "awaiting_replacement"
    assert reassessed.waiting_for_replacement is True
    assert reassessed.recovery is not None
    assert reassessed.recovery.replacement_plan is not None

    replacement_auth = issue_production_replacement_authorization(
        reassessed.recovery.replacement_plan,
        "replacement-auth",
    )
    transport.fail_at = 999
    completed = adapter.resume(replacement_auth)

    assert completed.state == "recovery_complete"
    assert completed.phase == "recovery_complete"
    assert completed.required_authorizations == ()
    assert adapter.complete is True


def test_runtime_adapter_rejects_wrong_type_for_authorized_plan():
    adapter = UnrealProductionRuntimeAdapter(
        UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "runtime-adapter-type-test"))
    )
    with pytest.raises(TypeError, match="UnrealAuthorizedProductionPlan"):
        adapter.start(object())


def test_runtime_adapter_exposes_snapshot_without_exposing_internal_loop():
    adapter = UnrealProductionRuntimeAdapter(
        UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "runtime-adapter-encapsulation-test"))
    )
    assert not hasattr(adapter, "loop")
    assert adapter.snapshot.state == "not_started"
