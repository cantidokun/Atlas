"""Tests for the agent-facing Unreal production controller boundary."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_recovery import (
    build_production_reassessment_plan,
    issue_production_replacement_authorization,
)
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _production():
    return build_unreal_production_plan(_intent(), _spec())


def _integration(transport):
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "controller-integration-test"))
    return UnrealProductionControllerIntegration(UnrealProductionRuntimeAdapter(executor))


def test_integration_completes_successful_production_and_has_no_next_authorization():
    production = _production()
    integration = _integration(ProductionTransport())
    event = integration.start(authorize_production_plan(production, "production-auth"))

    assert event.operation == "start"
    assert event.snapshot.state == "complete"
    assert integration.complete is True
    assert integration.next_required_authorization() is None


def test_integration_exposes_reassessment_as_the_only_next_authorization():
    production = _production()
    integration = _integration(ProductionTransport(fail_at=20))
    event = integration.start(authorize_production_plan(production, "production-auth"))

    assert event.snapshot.state == "awaiting_reassessment"
    assert event.snapshot.required_authorizations == ("reassessment",)
    assert integration.next_required_authorization() == "reassessment"


def test_integration_exposes_replacement_after_fresh_reassessment():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    integration = _integration(transport)
    integration.start(authorize_production_plan(production, "production-auth"))

    reassessment_plan = build_production_reassessment_plan(
        production,
        integration._runtime.loop._failure,
    )
    event = integration.reassess(
        UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    )

    assert event.operation == "reassess"
    assert event.snapshot.state == "awaiting_replacement"
    assert integration.next_required_authorization() == "replacement"
    assert event.snapshot.recovery.replacement_plan is not None


def test_integration_resumes_exact_replacement_and_clears_authorization_requirement():
    production = _production()
    transport = ProductionTransport(fail_at=20)
    integration = _integration(transport)
    integration.start(authorize_production_plan(production, "production-auth"))

    failure = integration._runtime.loop._failure
    reassessment_plan = build_production_reassessment_plan(production, failure)
    integration.reassess(UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth"))
    prepared = integration._runtime.loop._prepared_recovery
    replacement_auth = issue_production_replacement_authorization(
        prepared.replacement_plan,
        "replacement-auth",
    )
    transport.fail_at = 999

    event = integration.resume(replacement_auth)

    assert event.operation == "resume_recovery"
    assert event.snapshot.state == "recovery_complete"
    assert integration.complete is True
    assert integration.next_required_authorization() is None


def test_integration_rejects_non_runtime_dependencies():
    with pytest.raises(TypeError, match="runtime must be a UnrealProductionRuntimeAdapter"):
        UnrealProductionControllerIntegration(object())
