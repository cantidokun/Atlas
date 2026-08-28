"""Focused tests for the production-aware autonomous Unreal loop."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_autonomous_loop import UnrealProductionAutonomousLoop
from planning.unreal_production_controller_bridge import UnrealProductionControllerBridge
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_recovery import (
    build_production_reassessment_plan,
    issue_production_replacement_authorization,
)
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _production():
    return build_unreal_production_plan(_intent(), _spec())


def _loop(transport):
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "production-autonomous-loop-test"))
    return UnrealProductionAutonomousLoop(UnrealProductionControllerBridge(executor))


def test_loop_completes_authorized_production_without_recovery():
    production = _production()
    authorized = authorize_production_plan(production, "production-auth")
    outcome = _loop(ProductionTransport()).start(authorized)

    assert outcome.state == "complete"
    assert outcome.phase == "complete"
    assert outcome.required_authorizations == ()


def test_loop_stops_at_failure_and_surfaces_reassessment_requirement():
    production = _production()
    authorized = authorize_production_plan(production, "production-auth")
    outcome = _loop(ProductionTransport(fail_at=20)).start(authorized)

    assert outcome.state == "awaiting_reassessment"
    assert outcome.phase == "render"
    assert outcome.failure is not None
    assert outcome.required_authorizations == ("reassessment",)


def test_loop_reassesses_then_surfaces_exact_replacement_requirement():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    loop = _loop(transport)
    authorized = authorize_production_plan(production, "production-auth")
    started = loop.start(authorized)
    assert started.failure is not None

    reassessment_plan = build_production_reassessment_plan(production, started.failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")

    reassessed = loop.reassess(reassessment_auth)
    assert reassessed.state == "awaiting_replacement"
    assert reassessed.recovery is not None
    assert reassessed.recovery.replacement_plan is not None
    assert reassessed.required_authorizations == ("replacement",)


def test_loop_resumes_with_exact_replacement_authorization_without_repeating_reassessment():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    loop = _loop(transport)
    authorized = authorize_production_plan(production, "production-auth")
    started = loop.start(authorized)
    assert started.failure is not None

    reassessment_plan = build_production_reassessment_plan(production, started.failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    reassessed = loop.reassess(reassessment_auth)
    prepared = reassessed.recovery
    assert prepared is not None
    assert prepared.replacement_plan is not None

    replacement_auth = issue_production_replacement_authorization(
        prepared.replacement_plan,
        "replacement-auth",
    )
    calls_after_reassessment = list(transport.calls)
    transport.fail_at = 999

    completed = loop.resume_recovery(replacement_auth)

    assert completed.state == "recovery_complete"
    assert completed.phase == "recovery_complete"
    assert completed.required_authorizations == ()
    assert loop._bridge.complete is True
    assert transport.calls[: len(calls_after_reassessment)] == calls_after_reassessment


def test_loop_rejects_replacement_before_reassessment():
    production = _production()
    authorized = authorize_production_plan(production, "production-auth")
    loop = _loop(ProductionTransport(fail_at=20))
    loop.start(authorized)

    with pytest.raises(RuntimeError, match="not waiting for replacement"):
        loop.resume_recovery(UnrealPlanAuthorization.issue(production.plan, "wrong-auth"))
